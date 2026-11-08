<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
$root='/srv/zoco/public_html/manage';
$expected=['views/laser-maze.php'=>'95fd60f913a15a2d2eea309ba1b88a3d0a4db4b768e3babda2c585b5ea583cfe','assets/maintenance.css'=>'c8f400f493f62421114761e07ba1f4c0ad0fd267d6777f2eb73b48f2b34ad40e','assets/maintenance.js'=>'290b7facd3a265868ba946a6fcc2cbba09f9476f59e7563f422446b1f810d67b','maintenance-api.php'=>'bd6a2b8ec51576fd6745f11b18d141080ee9dba44de0fd9ec26e336a43efd6a9','maintenance.php'=>'836eed86cfb87c6fbe89d57b1f3d59141e63318d077c3ffd1c941dc0a46572ef','maintenance-lib.php'=>'639eb2a692cb69a29841bbc25a3a21955de8229b231b120b8da376525afd046b'];
$backup=__DIR__.'/backup-'.date('Ymd-His').'-'.bin2hex(random_bytes(3));$temps=[];$changed=[];
try{
 $same=true;foreach($expected as $name=>$hash)if(hash_file('sha256',$root.'/'.$name)!==hash_file('sha256',__DIR__.'/public/'.$name))$same=false;
 if($same){echo "Layout already installed.\n";exit;}
 foreach($expected as $name=>$hash)if(hash_file('sha256',$root.'/'.$name)!==$hash)throw new RuntimeException('Live source changed: '.$name);
 foreach(array_keys($expected) as $name)if(str_ends_with($name,'.php')){$output=[];exec(escapeshellarg(PHP_BINARY).' -l '.escapeshellarg(__DIR__.'/public/'.$name),$output,$status);if($status!==0)throw new RuntimeException('PHP syntax check failed');}
 if(!mkdir($backup,0700))throw new RuntimeException('Backup failed');
 foreach($expected as $name=>$hash){if(!is_dir(dirname($backup.'/'.$name)))mkdir(dirname($backup.'/'.$name),0700,true);if(!copy($root.'/'.$name,$backup.'/'.$name))throw new RuntimeException('Backup failed');chmod($backup.'/'.$name,0600);$temps[$name]=tempnam(dirname($root.'/'.$name),'.layout-');if(!copy(__DIR__.'/public/'.$name,$temps[$name])||!chmod($temps[$name],0644))throw new RuntimeException('Stage failed');}
 foreach(array_reverse(array_keys($expected)) as $name){if(!rename($temps[$name],$root.'/'.$name))throw new RuntimeException('Activation failed');unset($temps[$name]);$changed[]=$name;}
 echo "Maintenance calibration/control update installed. Private file backup: $backup\n";
}catch(Throwable $e){foreach(array_reverse($changed) as $name)copy($backup.'/'.$name,$root.'/'.$name);foreach($temps as $tmp)@unlink($tmp);fwrite(STDERR,'Update stopped: '.$e->getMessage()."\n");exit(1);}
