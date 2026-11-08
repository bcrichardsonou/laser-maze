<?php
require __DIR__.'/lib.php';require_once __DIR__.'/maintenance-lib.php';transport();session_boot();cfg();$u=require_admin();
if($_SERVER['REQUEST_METHOD']==='GET' && isset($_GET['status'])){
    $cid=filter_var($_GET['status'],FILTER_VALIDATE_INT);$c=$cid?one('SELECT * FROM zp_components WHERE id=?',[$cid]):null;
    if(!$c||!maintenance_enabled((int)$cid))json_reply(404,['error'=>'Component unavailable']);
    $rows=maintenance_rows((int)$cid);json_reply(200,['commands'=>$rows,'state'=>maintenance_view_state($c,$rows)]);
}
if($_SERVER['REQUEST_METHOD']!=='POST')fail(405,'POST required');csrf_check();limit('maintenance:admin:'.$u['id'],30,60);
$cid=id_input('component_id');$action=text_input('command',40);$params=[];
if($action==='audio_play')$params=['clip'=>text_input('clip',30)];
if($action==='rgb_test')$params=['color'=>text_input('color',10)];
if($action==='audio_mute'){if(!in_array($_POST['muted'] ?? null,['0','1'],true))fail(400,'Invalid mute setting');$params=['muted'=>$_POST['muted']==='1'];}
$ajax=($_SERVER['HTTP_ACCEPT'] ?? '')==='application/json';
try{$id=maintenance_enqueue($u,$cid,$action,$params);}catch(InvalidArgumentException $e){if($ajax)json_reply(409,['error'=>$e->getMessage()]);$c=one('SELECT exhibit_id FROM zp_components WHERE id=?',[$cid]);$_SESSION['maintenance_notice']=$e->getMessage();redirect('/?page=exhibit&id='.(int)$c['exhibit_id'].'#exhibit-'.(int)$c['exhibit_id'].'-maintenance');}
if($ajax)json_reply(200,['id'=>$id,'message'=>'Request sent. Waiting for the controller.']);
$c=one('SELECT exhibit_id FROM zp_components WHERE id=?',[$cid]);redirect('/?page=exhibit&id='.(int)$c['exhibit_id'].'#exhibit-'.(int)$c['exhibit_id'].'-maintenance');
