<?php
if(PHP_SAPI!=='cli')exit(1);
$p='/srv/zoco/public_html/manage/release-lib.php';$new=__DIR__.'/release-lib.php';
if(hash_file('sha256',$p)===hash_file('sha256',$new)){echo "Archive validator already updated.\n";exit;}
if(hash_file('sha256',$p)!=='b8c1eab8374ad0ed54ca2e96b319f1e83e2df05e54cc394900ef3e8f3e78ccd9')throw new RuntimeException('Live validator changed');
require $new;
$m=['format'=>1,'version'=>'test','firmware_version'=>'bench-test','python_version'=>'bench-test','notes'=>'test','fqbn'=>'arduino:avr:mega:cpu=atmega2560','files'=>[]];
for($i=0;$i<64;$i++)$m['files']['source/test'.$i.'.py']=str_repeat('a',64);
if(!release_manifest($m))throw new RuntimeException('64-file validation failed');
$m['files']['source/test64.py']=str_repeat('a',64);if(release_manifest($m))throw new RuntimeException('Upper limit failed');
unset($m['files']['source/test64.py']);$m['files']['source/../bad.py']=str_repeat('a',64);unset($m['files']['source/test63.py']);if(release_manifest($m))throw new RuntimeException('Traversal guard failed');
$output=[];exec(escapeshellarg(PHP_BINARY).' -l '.escapeshellarg($new),$output,$status);if($status!==0)throw new RuntimeException('Syntax failed');
$b=__DIR__.'/release-lib.backup-'.date('Ymd-His').'.php';if(!copy($p,$b)||!chmod($b,0600))throw new RuntimeException('Backup failed');
$tmp=tempnam(dirname($p),'.release-limit-');if(!copy($new,$tmp)||!chmod($tmp,0644)||!rename($tmp,$p))throw new RuntimeException('Install failed');
echo "Bounded archive limit raised to64; size/path/checksum constraints retained. Backup: $b\n";
