<?php
if(PHP_SAPI!=='cli')exit(1);
$root='/srv/zoco/public_html/manage';$expected=['views/laser-maze.php'=>'f3e46a5032433139f34ca3ae9ebb5f5a2bdf809f95f9e965510525a02f61e7df','assets/laser-maze.css'=>'bcebcb68c445d4742ee7a856700483cf06697ad045faf42c1b601771f54d4d43','fluid-lib.php'=>null,'fluid-status.php'=>null,'assets/fluid-level.js'=>null];$temps=[];$changed=[];
try{
 $same=true;foreach($expected as $n=>$h)if(!is_file($root.'/'.$n)||hash_file('sha256',$root.'/'.$n)!==hash_file('sha256',__DIR__.'/public/'.$n))$same=false;
 if($same){echo "Fluid overview already installed.\n";exit;}
 foreach($expected as $n=>$h)if($h===null?file_exists($root.'/'.$n):hash_file('sha256',$root.'/'.$n)!==$h)throw new RuntimeException('Live source changed: '.$n);
 foreach($expected as $n=>$h)if(str_ends_with($n,'.php')){$o=[];exec(escapeshellarg(PHP_BINARY).' -l '.escapeshellarg(__DIR__.'/public/'.$n),$o,$code);if($code!==0)throw new RuntimeException('Syntax failed');}
 $backup=__DIR__.'/backup-'.date('Ymd-His').'-'.bin2hex(random_bytes(3));if(!mkdir($backup,0700))throw new RuntimeException('Backup failed');
 foreach($expected as $n=>$h){if($h!==null){if(!is_dir(dirname($backup.'/'.$n)))mkdir(dirname($backup.'/'.$n),0700,true);if(!copy($root.'/'.$n,$backup.'/'.$n)||!chmod($backup.'/'.$n,0600))throw new RuntimeException('Backup failed');}$temps[$n]=tempnam(dirname($root.'/'.$n),'.fluid-');if(!copy(__DIR__.'/public/'.$n,$temps[$n])||!chmod($temps[$n],0644))throw new RuntimeException('Stage failed');}
 foreach(['fluid-lib.php','fluid-status.php','assets/fluid-level.js','assets/laser-maze.css','views/laser-maze.php'] as $n){if(!rename($temps[$n],$root.'/'.$n))throw new RuntimeException('Activation failed');unset($temps[$n]);$changed[]=$n;}
 echo "Public and logged-in fluid overview installed. Backup: $backup\n";
}catch(Throwable $e){foreach(array_reverse($changed) as $n){if($expected[$n]===null)unlink($root.'/'.$n);else copy($backup.'/'.$n,$root.'/'.$n);}foreach($temps as $t)@unlink($t);fwrite(STDERR,$e->getMessage()."\n");exit(1);}
