<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
$root='/srv/zoco/public_html/manage';
$expected=['maintenance-lib.php'=>'2b90c1f191662dc58a7103f82e24f6fc7b22ae1302bb9cce65986393b09ea2b2','maintenance.php'=>'8965ab3098e5131754dc780f41d270318eccdd3fa721cc548f591dfaadbff90e','assets/maintenance.js'=>'44412271c2e8055108dda6f009cb652a1596bb53780040e0ecf41ee4875ab353','assets/maintenance.css'=>'b541cb5fb40e63a673ea76b55ce558bf40f06d81a5ecea005aa4c2214cb43f9c'];
$backup=__DIR__.'/backup-'.date('Ymd-His').'-'.bin2hex(random_bytes(3));$temps=[];$changed=[];
try{
 $same=true;foreach($expected as $name=>$hash)if(hash_file('sha256',$root.'/'.$name)!==hash_file('sha256',__DIR__.'/public/'.$name))$same=false;
 if($same){echo "Hazer DMX controls already installed.\n";exit;}
 foreach($expected as $name=>$hash)if(hash_file('sha256',$root.'/'.$name)!==$hash)throw new RuntimeException('Live source changed: '.$name);
 foreach(array_keys($expected) as $name)if(str_ends_with($name,'.php')){$output=[];exec(escapeshellarg(PHP_BINARY).' -l '.escapeshellarg(__DIR__.'/public/'.$name),$output,$status);if($status!==0)throw new RuntimeException('PHP syntax check failed');}
 if(!mkdir($backup,0700))throw new RuntimeException('Backup failed');
 foreach($expected as $name=>$hash){if(!is_dir(dirname($backup.'/'.$name)))mkdir(dirname($backup.'/'.$name),0700,true);if(!copy($root.'/'.$name,$backup.'/'.$name))throw new RuntimeException('Backup failed');chmod($backup.'/'.$name,0600);$temps[$name]=tempnam(dirname($root.'/'.$name),'.layout-');if(!copy(__DIR__.'/public/'.$name,$temps[$name])||!chmod($temps[$name],0644))throw new RuntimeException('Stage failed');}
 foreach(array_reverse(array_keys($expected)) as $name){if(!rename($temps[$name],$root.'/'.$name))throw new RuntimeException('Activation failed');unset($temps[$name]);$changed[]=$name;}
 echo "Hazer DMX controls installed. Private file backup: $backup\n";
}catch(Throwable $e){foreach(array_reverse($changed) as $name)copy($backup.'/'.$name,$root.'/'.$name);foreach($temps as $tmp)@unlink($tmp);fwrite(STDERR,'Update stopped: '.$e->getMessage()."\n");exit(1);}
