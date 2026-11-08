<?php
require __DIR__.'/lib.php';
require __DIR__.'/release-lib.php';
transport(); cfg();
if ($_SERVER['REQUEST_METHOD']!=='POST') json_reply(405,['error'=>'POST required']);
limit('release:ip:'.($_SERVER['REMOTE_ADDR'] ?? ''),120,60);
$raw=file_get_contents('php://input',false,null,0,12000001);
if ($raw===false || strlen($raw)>12000000) json_reply(413,['error'=>'Request too large']);
$b=json_decode($raw,true);
if (!is_array($b) || !is_string($b['device_id'] ?? null)) json_reply(400,['error'=>'Invalid request']);
$key=$_SERVER['HTTP_X_ZOCO_KEY'] ?? '';
$c=one('SELECT * FROM zp_components WHERE device_id=? AND active=1',[$b['device_id']]);
if (!$c || !is_string($key) || !hash_equals($c['key_hash'],hash('sha256',$key))) json_reply(401,['error'=>'Unauthorized']);
if (!in_array($c['device_id'],cfg()['release_components'] ?? [],true)) json_reply(403,['error'=>'Release archiving is not enabled for this component']);
limit('release:component:'.$c['id'],20,60);
try {
    db()->beginTransaction();
    $active=one('SELECT active FROM zp_components WHERE id=? FOR UPDATE',[$c['id']]);
    if (!$active || !$active['active']) {db()->rollBack();json_reply(401,['error'=>'Component retired']);}
    if (($b['action'] ?? '')==='archive') {
        $m=$b['manifest'] ?? null; $hash=$b['sha256'] ?? '';
        if (!release_manifest($m) || !is_string($hash) || !preg_match('/^[a-f0-9]{64}$/D',$hash) ||
            !is_string($b['archive'] ?? null)) {db()->rollBack();json_reply(400,['error'=>'Invalid release']);}
        $data=base64_decode($b['archive'],true);
        if ($data===false || strlen($data)<20 || strlen($data)>8000000 ||
            !str_starts_with($data,"\x1f\x8b") || !hash_equals($hash,hash('sha256',$data))) {
            db()->rollBack();json_reply(400,['error'=>'Archive checksum or size invalid']);
        }
        $encoded=json_encode($m,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES);
        $r=one('SELECT * FROM zp_releases WHERE component_id=? AND version=?',[$c['id'],$m['version']]);
        if ($r && ($r['sha256']!==$hash || json_decode($r['manifest'],true)!=$m)) {
            db()->rollBack();json_reply(409,['error'=>'Version already exists with different content']);
        }
        if (!$r) {
            $usage=one('SELECT COUNT(*) n,COALESCE(SUM(bytes),0) bytes FROM zp_releases WHERE component_id=?',[$c['id']]);
            if ((int)$usage['n']>=200 || (int)$usage['bytes']+strlen($data)>256000000) {
                db()->rollBack();json_reply(507,['error'=>'Component archive quota reached']);
            }
        }
        $path=release_path((int)$c['id'],$hash);
        if (!is_file($path)) {
            $tmp=tempnam(release_store(),'.archive-');
            if ($tmp===false) throw new RuntimeException('Cannot stage archive');
            try {
                chmod($tmp,0600);
                if (file_put_contents($tmp,$data,LOCK_EX)!==strlen($data) || !rename($tmp,$path)) throw new RuntimeException('Cannot save archive');
            } finally {if (is_file($tmp)) unlink($tmp);}
        }
        if (!hash_equals($hash,hash_file('sha256',$path))) throw new RuntimeException('Stored archive mismatch');
        if (!$r) q('INSERT INTO zp_releases(component_id,version,sha256,manifest,bytes) VALUES (?,?,?,?,?)',[$c['id'],$m['version'],$hash,$encoded,strlen($data)]);
        db()->commit(); json_reply(200,['archived'=>$m['version'],'sha256'=>$hash]);
    }
    if (($b['action'] ?? '')!=='deployment' || !release_version($b['version'] ?? null) ||
        !is_string($b['deployment_id'] ?? null) || !preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/D',$b['deployment_id']) ||
        !in_array($b['status'] ?? '',['started','failed','verified'],true)) {
        db()->rollBack();json_reply(400,['error'=>'Invalid deployment']);
    }
    $r=one('SELECT * FROM zp_releases WHERE component_id=? AND version=?',[$c['id'],$b['version']]);
    if (!$r) {db()->rollBack();json_reply(409,['error'=>'Archive release first']);}
    $m=json_decode($r['manifest'],true);
    $fw=$b['firmware_version'] ?? null;$py=$b['python_version'] ?? null;$reason=$b['reason'] ?? null;
    if (($fw!==null && !release_version($fw)) || ($py!==null && !release_version($py)) ||
        ($reason!==null && (!is_string($reason) || !preg_match('/^[A-Za-z0-9_]{1,80}$/D',$reason))) ||
        ($b['status']==='verified' && ($fw!==$m['firmware_version'] || $py!==$m['python_version']))) {
        db()->rollBack();json_reply(400,['error'=>'Version verification mismatch']);
    }
    $d=one('SELECT * FROM zp_deployments WHERE component_id=? AND deployment_id=?',[$c['id'],$b['deployment_id']]);
    if ($d && ((int)$d['release_id']!==(int)$r['id'] ||
        ($d['status']!=='started' && $d['status']!==$b['status'] && $b['status']!=='started'))) {
        db()->rollBack();json_reply(409,['error'=>'Conflicting deployment record']);
    }
    if (!$d) q('INSERT INTO zp_deployments(component_id,deployment_id,release_id,status,firmware_version,python_version,reason) VALUES (?,?,?,?,?,?,?)',[$c['id'],$b['deployment_id'],$r['id'],$b['status'],$fw,$py,$reason]);
    elseif ($d['status']==='started' && $b['status']!=='started') q('UPDATE zp_deployments SET status=?,firmware_version=?,python_version=?,reason=?,updated_at=CURRENT_TIMESTAMP WHERE component_id=? AND deployment_id=?',[$b['status'],$fw,$py,$reason,$c['id'],$b['deployment_id']]);
    db()->commit();json_reply(200,['deployment_id'=>$b['deployment_id'],'accepted'=>$b['status']]);
} catch(Throwable $e) {
    if (db()->inTransaction()) db()->rollBack();
    error_log('ZoCo release storage failure: '.get_class($e));
    json_reply(503,['error'=>'Release storage unavailable']);
}
