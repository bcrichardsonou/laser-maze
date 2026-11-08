<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
$root='/srv/zoco/public_html/manage';
$expected=['maintenance-lib.php'=>'2bc7363f7308ebd56918c49d923568a62a7da58fda4b092f08c6d6ae08189b80','maintenance.php'=>'f2aec28b65252c81d05fb1172ed0b09874a14d03bb87b79561bbfe27185e76cd','assets/maintenance.js'=>'aaf33053b0bdfb1578cab53c9ee71b8e047684a3f22603d3c68eeeb3e0e53809'];
$backup=__DIR__.'/backup-'.date('Ymd-His').'-'.bin2hex(random_bytes(3));$temps=[];$changed=[];
try{
 $same=true;foreach($expected as $name=>$hash)if(hash_file('sha256',$root.'/'.$name)!==hash_file('sha256',__DIR__.'/public/'.$name))$same=false;
 if($same){echo "Alignment selector already installed.\n";exit;}
 foreach($expected as $name=>$hash)if(hash_file('sha256',$root.'/'.$name)!==$hash)throw new RuntimeException('Live source changed: '.$name);
 foreach(array_keys($expected) as $name)if(str_ends_with($name,'.php')){$output=[];exec(escapeshellarg(PHP_BINARY).' -l '.escapeshellarg(__DIR__.'/public/'.$name),$output,$status);if($status!==0)throw new RuntimeException('PHP syntax check failed');}
 if(!mkdir($backup,0700))throw new RuntimeException('Backup failed');
 foreach($expected as $name=>$hash){if(!is_dir(dirname($backup.'/'.$name)))mkdir(dirname($backup.'/'.$name),0700,true);if(!copy($root.'/'.$name,$backup.'/'.$name))throw new RuntimeException('Backup failed');chmod($backup.'/'.$name,0600);$temps[$name]=tempnam(dirname($root.'/'.$name),'.layout-');if(!copy(__DIR__.'/public/'.$name,$temps[$name])||!chmod($temps[$name],0644))throw new RuntimeException('Stage failed');}
 foreach(array_reverse(array_keys($expected)) as $name){if(!rename($temps[$name],$root.'/'.$name))throw new RuntimeException('Activation failed');unset($temps[$name]);$changed[]=$name;}
 echo "Laser alignment and calibration selectors installed. Private file backup: $backup\n";
}catch(Throwable $e){foreach(array_reverse($changed) as $name)copy($backup.'/'.$name,$root.'/'.$name);foreach($temps as $tmp)@unlink($tmp);fwrite(STDERR,'Update stopped: '.$e->getMessage()."\n");exit(1);}
