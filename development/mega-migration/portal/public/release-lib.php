<?php
declare(strict_types=1);
function release_version($s): bool { return is_string($s) && preg_match('/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/D',$s)===1; }
function release_manifest($m): bool {
    if (!is_array($m) || ($m['format'] ?? null)!==1 || !release_version($m['version'] ?? null) ||
        !release_version($m['firmware_version'] ?? null) || !release_version($m['python_version'] ?? null) ||
        !is_string($m['notes'] ?? null) || strlen($m['notes'])>2000 ||
        !in_array($m['fqbn'] ?? null,['arduino:renesas_uno:minima','arduino:avr:mega:cpu=atmega2560'],true) || !is_array($m['files'] ?? null) ||
        count($m['files'])<3 || count($m['files'])>40) return false;
    foreach($m['files'] as $path=>$hash) {
        if (!is_string($path) || strlen($path)>240 || str_contains($path,'..') ||
            !preg_match('#^(source|compiled)/[A-Za-z0-9_./-]+$#D',$path) ||
            !is_string($hash) || !preg_match('/^[a-f0-9]{64}$/D',$hash)) return false;
    }
    return true;
}
function release_store(): string {
    $dir=cfg()['release_storage'] ?? '';
    $real=is_string($dir) ? realpath($dir) : false;
    $root=realpath($_SERVER['DOCUMENT_ROOT'] ?? __DIR__);
    if (!$real || !$root || !is_dir($real) || !is_writable($real) ||
        $real===$root || str_starts_with($real,$root.DIRECTORY_SEPARATOR))
        throw new RuntimeException('Configure a private writable release_storage outside the website');
    return $real;
}
function release_path(int $cid,string $hash): string {
    if (!preg_match('/^[a-f0-9]{64}$/D',$hash)) throw new InvalidArgumentException('Invalid archive hash');
    return release_store().'/'.$cid.'-'.$hash.'.tar.gz';
}
