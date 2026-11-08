<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli')exit(1);
$live=['sampled_at'=>time(),'capabilities'=>['module_count'=>1,'powered_calibration'=>true]];
function one($sql,$args=[]){global $live;return $live?['value'=>json_encode(['received_at'=>time(),'data'=>$live])]:null;}
function esc($s){return htmlspecialchars((string)$s,ENT_QUOTES,'UTF-8');}
function csrf_field(){return '<input type="hidden" name="csrf" value="preview-only">';}
require __DIR__.'/public/maintenance-lib.php';
$count=0;
function check($ok,$why){global $count;if(!$ok)throw new RuntimeException($why);$count++;}
function rejected($p){try{maintenance_module_action(5,$p);return false;}catch(InvalidArgumentException $e){return true;}}
foreach(['selected','all'] as $scope){
 check(maintenance_module_action(5,['scope'=>$scope,'module'=>1,'high'=>true])==='laser_align','Timed HIGH mapping');
 check(maintenance_module_action(5,['scope'=>$scope,'module'=>1,'high'=>false])==='stop_game','LOW mapping');
}
check(rejected(['scope'=>'selected','module'=>2,'high'=>true]),'Unconfigured module rejected');
check(rejected(['scope'=>'all','module'=>1,'high'=>'1']),'Strict boolean');
check(rejected(['scope'=>'other','module'=>1,'high'=>true]),'Scope allowlist');
check(rejected(['scope'=>'selected','module'=>1,'high'=>true,'extra'=>1]),'Unknown params rejected');
$live['capabilities']['module_count']=15;
check(rejected(['scope'=>'all','module'=>1,'high'=>true]),'Future unsupported multi-module controller fails closed');
$live=null;
check(rejected(['scope'=>'selected','module'=>1,'high'=>true]),'Fresh capabilities required');
check(maintenance_module_action(5,['scope'=>'all','module'=>1,'high'=>false])==='stop_game','Global LOW remains available without capabilities');
$live=['sampled_at'=>1,'capabilities'=>['module_count'=>1,'powered_calibration'=>true]];
check(rejected(['scope'=>'all','module'=>1,'high'=>true]),'Stale controller data rejected');
$live=['sampled_at'=>time(),'capabilities'=>['module_count'=>1,'powered_calibration'=>true]];
maintenance_channel_target(5,1);check(true,'Channel1 accepted');try{maintenance_channel_target(5,2);check(false,'Wrong channel accepted');}catch(InvalidArgumentException $e){check(true,'Wrong channel rejected');}
$cid=5;$v2Locked=false;$ready=true;$testLocked=false;
$source=file_get_contents(__DIR__.'/public/maintenance-lib.php');
$start=strpos($source,'        $moduleLive=');$end=strpos($source,"        maintenance_group('Game settings'",$start);
ob_start();eval(substr($source,$start,$end-$start));$html=ob_get_clean();
check(substr_count($html,'data-maintenance-command="module_control"')===4,'Four HIGH/LOW controls');
check(str_contains($html,'data-module-select'),'Module selector');
check(!str_contains($html,'Set ring brightness')&&!str_contains($html,'Custom module color')&&!str_contains($html,'Select other ring animations'),'Unused ring options removed');
check(str_contains($html,'Entrance status light'),'Separate entrance indicator retained');
check(substr_count($html,'data-module-select')===3,'Three shared selectors');check(str_contains($html,'Laser module to align')&&str_contains($html,'Laser module to calibrate'),'Alignment and calibration selectors');check(substr_count($html,'name="module"')===7,'Selected channel posted by module, alignment and calibration forms');file_put_contents(__DIR__.'/preview-fragment.html',$html);
check(maintenance_parameters('receiver_auto',[])===[],'Empty auto parameters');try{maintenance_parameters('receiver_auto',['apply'=>true]);check(false,'Unexpected auto params');}catch(InvalidArgumentException $e){check(true,'Unexpected auto params rejected');}
check(substr_count($html,'data-maintenance-command="receiver_auto"')===1,'One auto-calibration button');check(!str_contains($html,'1 · Capture blocked beam')&&!str_contains($html,'Apply proposed thresholds'),'Manual capture workflow removed');check(str_contains($html,'Advanced · manual thresholds'),'Advanced manual controls collapsed');
echo "$count automatic-calibration portal checks passed.\n";
