<?php
declare(strict_types=1);
ini_set('display_errors', '0');
set_exception_handler(function(Throwable $e): void {
    error_log('ZoCo portal failure: '.get_class($e));
    http_response_code(503);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Portal unavailable. Check the private configuration, imported schema, and hosting error log.';
});
function cfg(): array {
    static $c;
    if ($c === null) {
        // Change this absolute path if the subdomain's folder is nested differently.
        $path = dirname(__DIR__, 2).'/zoco-portal-private/config.php';
        if (!is_file($path)) throw new RuntimeException('Missing configuration');
        $c = require $path;
        if (!is_array($c) || !preg_match('/^[a-f0-9]{64}$/iD', $c['encryption_key'] ?? '') ||
            !str_starts_with($c['base_url'] ?? '', 'https://')) throw new RuntimeException('Invalid configuration');
    }
    return $c;
}
function db(): PDO {
    static $p;
    if (!$p) {
        $c=cfg();
        $p=new PDO('mysql:host='.$c['db_host'].';dbname='.$c['db_name'].';charset=utf8mb4', $c['db_user'],$c['db_password'],[
            PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES=>false]);
        $p->exec("SET time_zone = '+00:00'");
    }
    return $p;
}
function q(string $sql,array $args=[]): PDOStatement { $s=db()->prepare($sql); $s->execute($args); return $s; }
function one(string $sql,array $args=[]): ?array { return q($sql,$args)->fetch() ?: null; }
function esc($s): string { return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
function fail(int $code,string $message): never { http_response_code($code); header('Content-Type: text/plain; charset=utf-8'); exit($message); }
function json_reply(int $code,array $data): never { http_response_code($code); header('Content-Type: application/json'); echo json_encode($data,JSON_THROW_ON_ERROR); exit; }
function transport(): void {
    if (empty($_SERVER['HTTPS']) || $_SERVER['HTTPS']==='off') fail(400,'HTTPS required. Ask Bluehost how HTTPS is exposed to PHP; do not disable this check.');
    header('Cache-Control: no-store'); header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: no-referrer'); header('X-Frame-Options: DENY');
    header("Content-Security-Policy: default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
}
function session_boot(): void {
    ini_set('session.use_strict_mode','1'); ini_set('session.use_only_cookies','1');
    session_name('__Host-zoco');
    session_set_cookie_params(['lifetime'=>0,'path'=>'/','secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
    session_start();
    if (!isset($_SESSION['csrf'])) $_SESSION['csrf']=bin2hex(random_bytes(32));
}
function csrf_field(): string { return '<input type="hidden" name="csrf" value="'.esc($_SESSION['csrf']).'">'; }
function csrf_check(): void {
    if (!is_string($_POST['csrf'] ?? null) || !hash_equals($_SESSION['csrf'],$_POST['csrf'])) fail(403,'Session expired. Reload the page.');
}
function redirect(string $path): never { header('Location: '.$path, true, 303); exit; }
function user(): ?array {
    if (empty($_SESSION['user_id'])) return null;
    $u=one('SELECT * FROM zp_users WHERE id=?',[ $_SESSION['user_id'] ]);
    if (!$u || !$u['active'] || (int)$u['session_version']!==($_SESSION['version'] ?? -1) ||
        time()-($_SESSION['signed_at'] ?? 0)>28800 || time()-($_SESSION['seen_at'] ?? 0)>3600) {
        unset($_SESSION['user_id'],$_SESSION['version']); return null;
    }
    $_SESSION['seen_at']=time(); return $u;
}
function require_user(): array { $u=user(); if (!$u) redirect('/?page=login'); return $u; }
function require_admin(): array { $u=require_user(); if ($u['role']!=='admin') fail(403,'Administrator access required.'); return $u; }
function allowed(array $u,int $exhibit,string $level='view'): bool {
    if ($u['role']==='admin') return true;
    $p=one('SELECT * FROM zp_permissions WHERE user_id=? AND exhibit_id=?',[$u['id'],$exhibit]);
    return $p && ($level==='view' || (in_array($level,['detail','control','manage'],true) && (bool)$p[$level]));
}
function audit(?int $uid,string $action,array $detail=[]): void { q('INSERT INTO zp_audit(user_id,action,details) VALUES (?,?,?)',[$uid,$action,json_encode($detail,JSON_THROW_ON_ERROR)]); }
function limit(string $name,int $max,int $seconds): void {
    $bucket=hash('sha256',$name); $now=time();
    q('INSERT INTO zp_limits(bucket,starts_at,attempts) VALUES (?,?,1) ON DUPLICATE KEY UPDATE attempts=IF(starts_at < ?,1,attempts+1), starts_at=IF(starts_at < ?,VALUES(starts_at),starts_at)',[$bucket,$now,$now-$seconds,$now-$seconds]);
    $r=one('SELECT attempts FROM zp_limits WHERE bucket=?',[$bucket]);
    if ((int)$r['attempts']>$max) { header('Retry-After: '.$seconds); fail(429,'Too many attempts. Please wait and try again.'); }
}
function ip_limit(string $action,int $max=20): void { limit($action.':ip:'.($_SERVER['REMOTE_ADDR'] ?? ''),$max,900); }
function text_input(string $key,int $max=160): string {
    $v=$_POST[$key] ?? null;
    if (!is_string($v) || strlen(trim($v))<1 || strlen(trim($v))>$max) fail(400,'Invalid '.$key); return trim($v);
}
function id_input(string $key): int { $s=$_POST[$key] ?? ''; if (!is_string($s) || !ctype_digit($s) || (int)$s<1) fail(400,'Invalid '.$key); return (int)$s; }
function location_row(int $id): array { return one('SELECT * FROM zp_locations WHERE id=?',[$id]) ?? throw new InvalidArgumentException('Unknown location'); }
function seal(string $plain): string {
    $iv=random_bytes(12); $tag=''; $encrypted=openssl_encrypt($plain,'aes-256-gcm',hex2bin(cfg()['encryption_key']),OPENSSL_RAW_DATA,$iv,$tag);
    if ($encrypted===false) throw new RuntimeException('Encryption failed'); return base64_encode($iv.$tag.$encrypted);
}
function unseal(string $encoded): string {
    $b=base64_decode($encoded,true); if ($b===false || strlen($b)<29) throw new RuntimeException('Invalid encrypted secret');
    $p=openssl_decrypt(substr($b,28),'aes-256-gcm',hex2bin(cfg()['encryption_key']),OPENSSL_RAW_DATA,substr($b,0,12),substr($b,12,16));
    if ($p===false) throw new RuntimeException('Cannot decrypt secret'); return $p;
}
function base32(string $raw): string {
    $bits=''; foreach (str_split($raw) as $c) $bits.=str_pad(decbin(ord($c)),8,'0',STR_PAD_LEFT);
    $out=''; foreach (str_split($bits,5) as $part) $out.='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'[bindec(str_pad($part,5,'0'))]; return $out;
}
function totp_step(string $secret,string $code): ?int {
    if (!preg_match('/^\d{6}$/D',$code)) return null;
    foreach ([-1,0,1] as $offset) {
        $step=intdiv(time(),30)+$offset; $hash=hash_hmac('sha1',pack('N2',0,$step),$secret,true);
        $i=ord($hash[19]) & 15; $value=unpack('N',substr($hash,$i,4))[1] & 0x7fffffff;
        if (hash_equals(str_pad((string)($value%1000000),6,'0',STR_PAD_LEFT),$code)) return $step;
    }
    return null;
}
function sign_in(array $u): never {
    session_regenerate_id(true); $_SESSION=['csrf'=>bin2hex(random_bytes(32)),'user_id'=>(int)$u['id'],'version'=>(int)$u['session_version'],'signed_at'=>time(),'seen_at'=>time()];
    audit((int)$u['id'],'login'); redirect('/');
}
function pending_user(): array {
    $p=$_SESSION['pending'] ?? null;
    if (!$p || time()-$p['at']>600) redirect('/?page=login');
    $u=one('SELECT * FROM zp_users WHERE id=?',[$p['id']]);
    if (!$u || !$u['active'] || (int)$u['session_version']!==$p['version']) redirect('/?page=login'); return $u;
}
function issue_link(int $uid): string {
    q('DELETE FROM zp_tokens WHERE user_id=?',[$uid]); $token=bin2hex(random_bytes(32));
    q('INSERT INTO zp_tokens(user_id,token_hash,expires_at) VALUES (?,?,DATE_ADD(UTC_TIMESTAMP(),INTERVAL 1 HOUR))',[$uid,hash('sha256',$token)]);
    return rtrim(cfg()['base_url'],'/').'/?page=password&token='.$token;
}
function send_link(string $email,string $link): bool {
    $c=cfg(); if (!$c['mail_enabled'] || !filter_var($c['mail_from'],FILTER_VALIDATE_EMAIL)) return false;
    return mail($email,'ZoCo portal account access',"Use this link within one hour to set your password:\n\n".$link."\n\nIf you did not request this, ignore it.",'From: '.$c['mail_from']);
}
function exhibits_for(array $u): array {
    $select='SELECT e.*,l.name location_name,l.timezone,m.name museum_name FROM zp_exhibits e JOIN zp_locations l ON l.id=e.location_id JOIN zp_museums m ON m.id=l.museum_id';
    return $u['role']==='admin' ? q($select.' WHERE e.active=1 ORDER BY e.name')->fetchAll() : q($select.' JOIN zp_permissions p ON p.exhibit_id=e.id WHERE p.user_id=? AND e.active=1 ORDER BY e.name',[$u['id']])->fetchAll();
}
function components(int $eid): array { return q('SELECT * FROM zp_components WHERE exhibit_id=? ORDER BY active DESC,name',[$eid])->fetchAll(); }
function summary(array $cs): string {
    $rank=['faulted'=>0,'maintenance'=>1,'unknown'=>2,'running'=>3,'ready'=>4,'intentionally_off'=>5]; $state='unknown'; $best=9;
    foreach ($cs as $c) if ($c['active'] && $rank[$c['state']]<$best) {$state=$c['state']; $best=$rank[$state];} return $state;
}
function stamp(?string $s,string $zone): string {
    if (!$s) return 'Not reported'; return (new DateTimeImmutable($s,new DateTimeZone('UTC')))->setTimezone(new DateTimeZone($zone))->format('M j, Y g:i:s a T');
}
function fresh(array $c): bool { return $c['last_contact'] && time()-(new DateTimeImmutable($c['last_contact'],new DateTimeZone('UTC')))->getTimestamp()<300; }
function header_page(string $title,?array $u=null): void {
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'.esc($title).' · ZoCo</title><link rel="stylesheet" href="/assets/portal.css"><link rel="stylesheet" href="/assets/exhibit-layout.css"><script src="/assets/exhibit-layout.js" defer></script></head><body><header><a class="brand" href="/">';
    if (is_file(__DIR__.'/assets/logo.png')) echo '<img src="/assets/logo.png" alt="ZoCo">'; else echo '<strong>ZoCo</strong>';
    echo '</a><span>Exhibit management</span>';
    if ($u) {echo '<nav><a href="/">Overview</a>'; if ($u['role']==='admin') echo '<a href="/?page=admin">Manage</a><a href="/releases.php">Software releases</a>'; echo '<span>'.esc($u['name']).'</span><form method="post">'.csrf_field().'<input type="hidden" name="action" value="logout"><button class="secondary">Sign out</button></form></nav>';}
    echo '</header><main>';
}
function footer_page(): void { echo '<footer>ZoCo monitoring · Maintenance controls require administrator access. Connection loss alone is not an exhibit fault.</footer></main></body></html>'; }

require_once __DIR__.'/maintenance-lib.php';
require_once __DIR__.'/views/exhibit.php';
