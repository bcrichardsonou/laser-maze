<?php
if(PHP_SAPI!=='cli')exit(1);
require __DIR__.'/public/maintenance-lib.php';
foreach(['laser_align','module_test'] as $a)if(maintenance_parameters($a,[])!==[])throw new RuntimeException('valid command rejected');
try{maintenance_parameters('laser_align',['seconds'=>999]);throw new RuntimeException('unexpected parameters accepted');}catch(InvalidArgumentException $e){}
if(!in_array('laser_align',MAINTENANCE_V2_ACTIONS,true))throw new RuntimeException('missing gated action');
echo "Alignment parameter checks passed.\n";
