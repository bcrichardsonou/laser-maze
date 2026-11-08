<?php
require __DIR__.'/lib.php';require_once __DIR__.'/maintenance-lib.php';transport();session_boot();cfg();$u=require_admin();
if($_SERVER['REQUEST_METHOD']==='GET' && isset($_GET['status'])){
    $cid=filter_var($_GET['status'],FILTER_VALIDATE_INT);$c=$cid?one('SELECT * FROM zp_components WHERE id=?',[$cid]):null;
    if(!$c||!maintenance_enabled((int)$cid))json_reply(404,['error'=>'Component unavailable']);
    $rows=maintenance_rows((int)$cid);json_reply(200,['commands'=>$rows,'state'=>maintenance_view_state($c,$rows),'live'=>maintenance_live((int)$cid)]);
}
if($_SERVER['REQUEST_METHOD']!=='POST')fail(405,'POST required');csrf_check();limit('maintenance:admin:'.$u['id'],30,60);
$cid=id_input('component_id');$action=text_input('command',40);$params=[];
if($action==='audio_play')$params=['clip'=>text_input('clip',30)];
if($action==='rgb_test')$params=['color'=>text_input('color',10)];
if($action==='audio_mute'){if(!in_array($_POST['muted'] ?? null,['0','1'],true))fail(400,'Invalid mute setting');$params=['muted'=>$_POST['muted']==='1'];}
if($action==='receiver_capture')$params=['phase'=>text_input('phase',20)];
if($action==='receiver_apply')$params=['candidate_id'=>text_input('candidate_id',36)];
if($action==='receiver_thresholds')$params=['break_below'=>filter_var($_POST['break_below'] ?? null,FILTER_VALIDATE_INT),'clear_above'=>filter_var($_POST['clear_above'] ?? null,FILTER_VALIDATE_INT)];
if($action==='audio_volume')$params=['percent'=>filter_var($_POST['percent'] ?? null,FILTER_VALIDATE_INT)];
if($action==='start_lock'){if(!in_array($_POST['locked'] ?? null,['0','1'],true))fail(400,'Invalid play lock');$params=['locked'=>$_POST['locked']==='1'];}
if($action==='game_settings'){
    foreach(['duration','startup','cooldown','warmup','max_breaks'] as $name)$params[$name]=filter_var($_POST[$name] ?? null,FILTER_VALIDATE_INT);
    $params['enabled_beams']=[($_POST['beam1'] ?? '')==='1',($_POST['beam2'] ?? '')==='1'];$params['available_modes']=$_POST['modes'] ?? [];
}
$ajax=($_SERVER['HTTP_ACCEPT'] ?? '')==='application/json';
try{if($action==='module_control')$action=maintenance_module_action($cid,['scope'=>text_input('scope',10),'module'=>filter_var($_POST['module'] ?? null,FILTER_VALIDATE_INT),'high'=>match($_POST['high'] ?? null){'1'=>true,'0'=>false,default=>null}]);if(in_array($action,['laser_align','receiver_auto','receiver_capture','receiver_apply','receiver_thresholds'],true))maintenance_channel_target($cid,filter_var($_POST['module'] ?? 1,FILTER_VALIDATE_INT));$id=maintenance_enqueue($u,$cid,$action,$params);}catch(InvalidArgumentException $e){if($ajax)json_reply(409,['error'=>$e->getMessage()]);$c=one('SELECT exhibit_id FROM zp_components WHERE id=?',[$cid]);$_SESSION['maintenance_notice']=$e->getMessage();redirect('/?page=exhibit&id='.(int)$c['exhibit_id'].'#exhibit-'.(int)$c['exhibit_id'].'-maintenance');}
if($ajax)json_reply(200,['id'=>$id,'message'=>'Request sent. Waiting for the controller.']);
$c=one('SELECT exhibit_id FROM zp_components WHERE id=?',[$cid]);redirect('/?page=exhibit&id='.(int)$c['exhibit_id'].'#exhibit-'.(int)$c['exhibit_id'].'-maintenance');
