<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
$root='/srv/zoco/public_html/manage';$expected=json_decode(file_get_contents(__DIR__.'/expected.json'),true,512,JSON_THROW_ON_ERROR);
$files=[];foreach(new RecursiveIteratorIterator(new RecursiveDirectoryIterator(__DIR__.'/public',FilesystemIterator::SKIP_DOTS)) as $f)if($f->isFile())$files[substr($f->getPathname(),strlen(__DIR__.'/public/'))]=$f->getPathname();
uksort($files,fn($a,$b)=>(($a==='lib.php'?2:(isset($expected[$a])?1:0))<=>($b==='lib.php'?2:(isset($expected[$b])?1:0))));
$backup=__DIR__.'/backup-'.date('Ymd-His').'-'.bin2hex(random_bytes(3));$changed=[];$temps=[];$dbStarted=false;
try{
    $same=true;foreach($files as $name=>$source)if(!is_file($root.'/'.$name)||hash_file('sha256',$source)!==hash_file('sha256',$root.'/'.$name))$same=false;
    if($same){echo "Maintenance update already installed.\n";exit;}
    foreach($files as $name=>$source){$target=$root.'/'.$name;if(isset($expected[$name])){if(!is_file($target)||hash_file('sha256',$target)!==$expected[$name])throw new RuntimeException('Live source changed: '.$name);}elseif(file_exists($target))throw new RuntimeException('Unexpected file: '.$name);
        if(str_ends_with($name,'.php')){$output=[];exec(escapeshellarg(PHP_BINARY).' -l '.escapeshellarg($source).' 2>&1',$output,$status);if($status!==0)throw new RuntimeException('Syntax validation failed: '.$name);}
    }
    if(!mkdir($backup,0700))throw new RuntimeException('Backup folder failed');
    foreach($files as $name=>$source){if(is_file($root.'/'.$name)){if(!is_dir(dirname($backup.'/'.$name)))mkdir(dirname($backup.'/'.$name),0700,true);if(!copy($root.'/'.$name,$backup.'/'.$name))throw new RuntimeException('File backup failed');chmod($backup.'/'.$name,0600);}
        $temp=tempnam(dirname($root.'/'.$name),'.maintenance-');$temps[$name]=$temp;if(!copy($source,$temp)||!chmod($temp,0644))throw new RuntimeException('Staging failed');
    }
    require $root.'/lib.php';
    $config=dirname($root,2).'/zoco-portal-private/config.php';if(!copy($config,$backup.'/config.php'))throw new RuntimeException('Config backup failed');chmod($backup.'/config.php',0600);
    $dbfile=$backup.'/portal-database.ndjson.gz';$gz=gzopen($dbfile.'.incomplete','wb6');if(!$gz)throw new RuntimeException('Database backup failed');chmod($dbfile.'.incomplete',0600);
    try{
        db()->beginTransaction();
        foreach(q('SHOW TABLES')->fetchAll() as $row){$table=(string)reset($row);if(!str_starts_with($table,'zp_'))continue;$quoted='`'.str_replace('`','``',$table).'`';
            $schema=q('SHOW CREATE TABLE '.$quoted)->fetch();if(gzwrite($gz,json_encode(['table'=>$table,'schema'=>$schema],JSON_THROW_ON_ERROR)."\n")===false)throw new RuntimeException('Database backup write failed');
            foreach(q('SELECT * FROM '.$quoted) as $data)if(gzwrite($gz,json_encode(['table'=>$table,'row'=>$data],JSON_THROW_ON_ERROR)."\n")===false)throw new RuntimeException('Database backup write failed');
        }db()->commit();
    }finally{gzclose($gz);if(db()->inTransaction())db()->rollBack();}
    if(!rename($dbfile.'.incomplete',$dbfile))throw new RuntimeException('Database backup finalization failed');
    db()->exec(file_get_contents(__DIR__.'/migration.sql'));
    $columns=array_column(q('SHOW COLUMNS FROM zp_commands')->fetchAll(),'Field');foreach(['id','component_id','requested_by','action','parameters','status','result','expires_at','created_at','updated_at'] as $name)if(!in_array($name,$columns,true))throw new RuntimeException('Existing command table is incompatible');
    $component=one('SELECT id FROM zp_components WHERE device_id=? AND active=1',['example-device']);if(!$component)throw new RuntimeException('Expected Laser Maze bench component is unavailable');
    db()->beginTransaction();$dbStarted=true;
    q('INSERT INTO zp_settings(name,value) VALUES (?,?) ON DUPLICATE KEY UPDATE value=VALUES(value)',['maintenance_component:'.$component['id'],'1']);
    foreach($files as $name=>$source){if(!rename($temps[$name],$root.'/'.$name))throw new RuntimeException('Activation failed: '.$name);$changed[]=$name;unset($temps[$name]);}
    audit(null,'maintenance_installed',['component_id'=>(int)$component['id']]);db()->commit();$dbStarted=false;
    echo "Maintenance portal installed for Laser Maze. Private database/config/file backup: $backup\nController support and command-delivery service still require Pi installation.\n";
}catch(Throwable $e){
    if(function_exists('db'))try{if(db()->inTransaction())db()->rollBack();}catch(Throwable $ignored){}
    foreach(array_reverse($changed) as $name){if(is_file($backup.'/'.$name))copy($backup.'/'.$name,$root.'/'.$name);else @unlink($root.'/'.$name);}
    foreach($temps as $path)@unlink($path);
    fwrite(STDERR,'Maintenance update stopped: '.($e instanceof PDOException?get_class($e):$e->getMessage())."\nChanged files restored; additive table may remain.\n");exit(1);
}
