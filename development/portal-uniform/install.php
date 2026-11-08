<?php
declare(strict_types=1);
if (PHP_SAPI!=='cli') {http_response_code(404);exit;}
$root='/srv/zoco/public_html/manage';
$expected=json_decode(file_get_contents(__DIR__.'/expected.json'),true,512,JSON_THROW_ON_ERROR);
$files=[];
$iter=new RecursiveIteratorIterator(new RecursiveDirectoryIterator(__DIR__.'/update',FilesystemIterator::SKIP_DOTS));
foreach($iter as $f)if($f->isFile())$files[substr($f->getPathname(),strlen(__DIR__.'/update/'))]=$f->getPathname();
$backup=__DIR__.'/backup-'.date('Ymd-His').'-'.bin2hex(random_bytes(3));$changed=[];$temps=[];
try {
    $same=true;foreach($files as $name=>$source)if(!is_file($root.'/'.$name)||!hash_equals(hash_file('sha256',$source),hash_file('sha256',$root.'/'.$name)))$same=false;
    if($same){echo "This update is already installed. No links changed.\n";exit(0);}
    foreach($files as $name=>$source){$target=$root.'/'.$name;if(isset($expected[$name])){if(!is_file($target)||!hash_equals($expected[$name],hash_file('sha256',$target)))throw new RuntimeException('Current file changed; obtain a fresh snapshot: '.$name);}elseif(file_exists($target))throw new RuntimeException('Unexpected existing file: '.$name);
        if(str_ends_with($name,'.php')){$output=[];exec(escapeshellarg(PHP_BINARY).' -l '.escapeshellarg($source).' 2>&1',$output,$code);if($code!==0)throw new RuntimeException('PHP validation failed: '.$name);}
    }
    if(!mkdir($backup,0700))throw new RuntimeException('Cannot create backup');
    foreach($files as $name=>$source){$target=$root.'/'.$name;if(is_file($target)){if(!is_dir(dirname($backup.'/'.$name)))mkdir(dirname($backup.'/'.$name),0700,true);if(!copy($target,$backup.'/'.$name))throw new RuntimeException('Backup failed: '.$name);chmod($backup.'/'.$name,0600);} $temp=tempnam(dirname($target),'.uniform-');$temps[$name]=$temp;if(!copy($source,$temp)||!chmod($temp,0644))throw new RuntimeException('Staging failed: '.$name);}
    // The existing private config and tables are reused; no schema reimport.
    require $root.'/lib.php';
    $snapshot=['shares'=>q('SELECT * FROM zp_shares')->fetchAll(),'viewing_settings'=>q("SELECT * FROM zp_settings WHERE name LIKE 'viewing_link:%'")->fetchAll()];
    $snapshotFile=$backup.'/viewing-links-before.json';if(file_put_contents($snapshotFile,json_encode($snapshot,JSON_THROW_ON_ERROR|JSON_PRETTY_PRINT))===false)throw new RuntimeException('Cannot save link backup');chmod($snapshotFile,0600);
    db()->beginTransaction();
    // New support helpers must load before activation/backfill; old lib loaded the old views.
    require_once __DIR__.'/update/views/exhibit-layout.php';
    $count=0;
    foreach(q('SELECT e.id,e.name FROM zp_exhibits e WHERE e.active=1 AND NOT EXISTS (SELECT 1 FROM zp_shares s WHERE s.exhibit_id=e.id)')->fetchAll() as $e){exhibit_share_create((int)$e['id'],null,$e['name']);$count++;}
    foreach($files as $name=>$source){if(!rename($temps[$name],$root.'/'.$name))throw new RuntimeException('Activation failed: '.$name);$changed[]=$name;unset($temps[$name]);}
    audit(null,'uniform_dashboard_install',['new_viewing_links'=>$count]);db()->commit();
    echo "Shared dashboards installed. Existing links preserved; $count default viewing links created for exhibits with no link history.\nPrivate backup: $backup\nRefresh both exhibit pages and test a viewing link from Manage.\n";
} catch(Throwable $e){
    if(function_exists('db')){try{if(db()->inTransaction())db()->rollBack();}catch(Throwable $ignored){}}
    foreach(array_reverse($changed) as $name){$old=$backup.'/'.$name;if(is_file($old))copy($old,$root.'/'.$name);else @unlink($root.'/'.$name);}
    foreach($temps as $temp)@unlink($temp);
    fwrite(STDERR,'Update stopped: '.$e->getMessage()."\nActivated files restored and uncommitted links rolled back.\n");exit(1);
}
