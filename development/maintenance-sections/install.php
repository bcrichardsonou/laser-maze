<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
$root='/srv/zoco/public_html/manage';
$expected=['maintenance-lib.php'=>'7b384b385a4ec5d924d76afd42aa976516cfcb5f4125cbff7bfa873155fac628','maintenance.php'=>'a7273b697a598196b9161e85d169b889880c05b0f1093a2f962214a4d8c99546','assets/maintenance.js'=>'0867f12bc8dc8363a8e6eddafc391b404aa028879583ae53edb2173fa8cd3672','assets/maintenance.css'=>'bf3829569054452623441c21e20749b93c3bfa53b5a896fa091451e5eccfd852'];
$backup=__DIR__.'/backup-'.date('Ymd-His').'-'.bin2hex(random_bytes(3));$temps=[];$changed=[];
try{
 $same=true;foreach($expected as $name=>$hash)if(hash_file('sha256',$root.'/'.$name)!==hash_file('sha256',__DIR__.'/public/'.$name))$same=false;
 if($same){echo "All maintenance section shortcuts already installed.\n";exit;}
 foreach($expected as $name=>$hash)if(hash_file('sha256',$root.'/'.$name)!==$hash)throw new RuntimeException('Live source changed: '.$name);
 foreach(array_keys($expected) as $name)if(str_ends_with($name,'.php')){$output=[];exec(escapeshellarg(PHP_BINARY).' -l '.escapeshellarg(__DIR__.'/public/'.$name),$output,$status);if($status!==0)throw new RuntimeException('PHP syntax check failed');}
 if(!mkdir($backup,0700))throw new RuntimeException('Backup failed');
 foreach($expected as $name=>$hash){if(!is_dir(dirname($backup.'/'.$name)))mkdir(dirname($backup.'/'.$name),0700,true);if(!copy($root.'/'.$name,$backup.'/'.$name))throw new RuntimeException('Backup failed');chmod($backup.'/'.$name,0600);$temps[$name]=tempnam(dirname($root.'/'.$name),'.layout-');if(!copy(__DIR__.'/public/'.$name,$temps[$name])||!chmod($temps[$name],0644))throw new RuntimeException('Stage failed');}
 foreach(array_reverse(array_keys($expected)) as $name){if(!rename($temps[$name],$root.'/'.$name))throw new RuntimeException('Activation failed');unset($temps[$name]);$changed[]=$name;}
 echo "All maintenance section shortcuts installed. Private file backup: $backup\n";
}catch(Throwable $e){foreach(array_reverse($changed) as $name)copy($backup.'/'.$name,$root.'/'.$name);foreach($temps as $tmp)@unlink($tmp);fwrite(STDERR,'Update stopped: '.$e->getMessage()."\n");exit(1);}
