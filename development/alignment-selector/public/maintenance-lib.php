<?php
const MAINTENANCE_ACTIONS=['enter_maintenance','leave_maintenance','stop_game','snapshot','audio_play','stop_audio','audio_mute','rgb_test','display_test','restart_game','receiver_capture','receiver_apply','receiver_thresholds','module_test','laser_align','game_settings','start_lock','audio_volume','audio_output_test','service_start','service_stop','reboot_pi','software_reinstall'];
const MAINTENANCE_CLIPS=['preparation'=>'Preparation','entrance'=>'Entrance','warning90'=>'90-second warning','warning30'=>'30-second warning','warning10'=>'10-second warning','beam'=>'Beam alarm','win_keys'=>'Key objective win','win_usb'=>'USB objective win','beam_loss'=>'Beam-limit loss','timeout'=>'Time up'];
const MAINTENANCE_V2_ACTIONS=['receiver_capture','receiver_apply','receiver_thresholds','module_test','laser_align','game_settings','start_lock','audio_volume','audio_output_test','service_start','service_stop','reboot_pi','software_reinstall'];
function maintenance_live(int $cid): ?array {
    $r=json_decode(one('SELECT value FROM zp_settings WHERE name=?',['maintenance_live:'.$cid])['value'] ?? '{}',true);
    $d=$r['data'] ?? null;
    if(!is_array($d)||!is_int($r['received_at'] ?? null)||time()-$r['received_at']>10||!is_int($d['sampled_at'] ?? null)||abs(time()-$d['sampled_at'])>10)return null;
    return $d;
}
function maintenance_parameters(string $action,array $p): array {
    if(!in_array($action,MAINTENANCE_ACTIONS,true))throw new InvalidArgumentException('Unsupported maintenance action');
    if($action==='audio_play'){if(array_keys($p)!==['clip']||!is_string($p['clip'])||!isset(MAINTENANCE_CLIPS[$p['clip']]))throw new InvalidArgumentException('Choose a known audio clip');return $p;}
    if($action==='audio_mute'){if(array_keys($p)!==['muted']||!is_bool($p['muted']))throw new InvalidArgumentException('Invalid mute setting');return $p;}
    if($action==='rgb_test'){if(array_keys($p)!==['color']||!in_array($p['color'],['RED','GREEN','BLUE','YELLOW','PURPLE','OFF'],true))throw new InvalidArgumentException('Choose a supported color');return $p;}
    if($action==='receiver_capture'){if(array_keys($p)!==['phase']||!in_array($p['phase'],['blocked','clear','blocked_check'],true))throw new InvalidArgumentException('Choose blocked, clear or blocked check');return $p;}
    if($action==='receiver_apply'){if(array_keys($p)!==['candidate_id']||!is_string($p['candidate_id'])||!preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/D',$p['candidate_id']))throw new InvalidArgumentException('Capture all three samples before applying');return $p;}
    if($action==='receiver_thresholds'){if(array_keys($p)!==['break_below','clear_above']||!is_int($p['break_below'])||!is_int($p['clear_above'])||!($p['break_below']>0&&$p['break_below']<$p['clear_above']&&$p['clear_above']<1023))throw new InvalidArgumentException('Thresholds must satisfy 0 < break < clear < 1023');return $p;}
    if($action==='start_lock'){if(array_keys($p)!==['locked']||!is_bool($p['locked']))throw new InvalidArgumentException('Invalid play lock');return $p;}
    if($action==='audio_volume'){if(array_keys($p)!==['percent']||!is_int($p['percent'])||$p['percent']<0||$p['percent']>100)throw new InvalidArgumentException('Volume must be 0–100');return $p;}
    if($action==='game_settings'){
        $ranges=['duration'=>[10,3600],'startup'=>[1,30],'cooldown'=>[1,60],'warmup'=>[1,30],'max_breaks'=>[1,20]];
        if(count($p)!==7)throw new InvalidArgumentException('Incomplete game settings');
        foreach($ranges as $key=>[$low,$high])if(!is_int($p[$key] ?? null)||$p[$key]<$low||$p[$key]>$high)throw new InvalidArgumentException('Invalid '.$key);
        $beams=$p['enabled_beams'] ?? null;$modes=$p['available_modes'] ?? null;
        if(!is_array($beams)||array_keys($beams)!==[0,1]||!is_bool($beams[0])||!is_bool($beams[1])||!in_array(true,$beams,true)||!is_array($modes)||!$modes||count($modes)!==count(array_unique($modes,SORT_REGULAR)))throw new InvalidArgumentException('Enable at least one beam and mode');
        foreach($modes as $mode)if(!is_string($mode)||!in_array($mode,['usb','usb-break-all','keys','keys-break-all'],true))throw new InvalidArgumentException('Invalid game mode');return $p;
    }
    if($p)throw new InvalidArgumentException('Unexpected command parameters');return [];
}
// Portal adapter: current controller has one real module and existing timed ON/global OFF commands.
function maintenance_module_action(int $cid,array $p): string {
    if(array_keys($p)!==['scope','module','high']||!in_array($p['scope'],['selected','all'],true)||!is_int($p['module'])||!is_bool($p['high']))throw new InvalidArgumentException('Invalid module selection');
    if($p['scope']==='all'&&!$p['high'])return 'stop_game';
    $live=maintenance_live($cid);
    if(($live['capabilities']['module_count'] ?? null)!==1||empty($live['capabilities']['powered_calibration']))throw new InvalidArgumentException('Waiting for a supported module controller. Only configured modules can be tested.');
    if($p['module']!==1)throw new InvalidArgumentException('This controller currently supports module 1 only');
    return $p['high']?'laser_align':'stop_game';
}
function maintenance_channel_target(int $cid,int $module): void {
    maintenance_module_action($cid,['scope'=>'selected','module'=>$module,'high'=>true]);
}
function maintenance_enabled(int $cid): bool {return (one('SELECT value FROM zp_settings WHERE name=?',['maintenance_component:'.$cid])['value'] ?? '')==='1';}
function maintenance_ready(array $c): bool {
    return $c['active'] && fresh($c) && $c['state_at'] && time()-(new DateTimeImmutable($c['state_at'],new DateTimeZone('UTC')))->getTimestamp()<=120 && in_array(dashboard_payload($c)['metrics']['maintenance_protocol'] ?? null,[1,2],true);
}
function maintenance_expire(int $cid): void {
    q("UPDATE zp_commands SET status=CASE WHEN status='requested' THEN 'expired' ELSE 'unconfirmed' END,updated_at=UTC_TIMESTAMP() WHERE component_id=? AND status IN ('requested','accepted') AND expires_at<=UTC_TIMESTAMP()",[$cid]);
}
function maintenance_view_state(array $c,array $rows): array {
    $ready=maintenance_ready($c);$m=dashboard_payload($c)['metrics'] ?? [];$live=maintenance_live((int)$c['id']);
    if($live&&($live['protocol'] ?? null)===2){$m=array_merge($m,$live);$ready=$c['active']&&($live['connected'] ?? false)===true;}
    $enabled=!empty($m['maintenance_enabled']);$local=!empty($m['maintenance_local_enabled']);
    if($live)$local=$enabled&&$local&&($live['local_until'] ?? 0)>time();
    $stateAt=$c['state_at']?(new DateTimeImmutable($c['state_at'],new DateTimeZone('UTC')))->getTimestamp():0;
    if($live)$stateAt=$live['sampled_at'];
    $newest=0;
    foreach($rows as $r){$result=json_decode($r['result'] ?? '{}',true);$at=$result['executed_at'] ?? 0;
        if($at>=$stateAt && $at>$newest && isset($result['snapshot']['maintenance_enabled'])){
            $newest=$at;$enabled=$result['snapshot']['maintenance_enabled']===true;$local=($result['snapshot']['maintenance_local_enabled'] ?? false)===true;
        }
    }
    $pending=array_values(array_filter($rows,fn($r)=>in_array($r['status'],['requested','accepted'],true)));
    $entry=false;foreach($pending as $r)if($r['action']==='enter_maintenance')$entry=true;
    if(!$ready)$label='Connection unconfirmed — waiting for a fresh controller report.';
    elseif($entry)$label='Waiting for local confirmation — press C on the exhibit keypad, or Exit maintenance to cancel.';
    elseif($pending)$label='Command in progress — wait for its result, or cancel with Stop game / Stop sound.';
    elseif($enabled&&$local)$label='Maintenance active — local tests enabled. D cancels tests; B exits maintenance.';
    elseif($enabled)$label='Maintenance active — tests locked. Press C on the exhibit keypad to renew the five-minute enable.';
    elseif(!empty($live['play_locked']))$label='New games disabled — enter maintenance to enable play again.';
    else $label='Normal operation — tests locked. Choose Enter maintenance, then press C on the exhibit keypad.';
    return ['ready'=>$ready,'enabled'=>$enabled,'local_enabled'=>$local,'pending'=>count($pending)>0,'entry_pending'=>$entry,'label'=>$label,'v2'=>($live['protocol'] ?? null)===2,'service_start_ready'=>($live['protocol'] ?? null)===2&&$c['active']&&in_array($live['service_state'] ?? '',['inactive','failed'],true)];
}
function maintenance_enqueue(array $u,int $cid,string $action,array $params): string {
    if(($u['role'] ?? '')!=='admin')throw new InvalidArgumentException('Administrator access required');
    $params=maintenance_parameters($action,$params);
    db()->beginTransaction();
    try {
        $c=one('SELECT * FROM zp_components WHERE id=? FOR UPDATE',[$cid]);
        if(!$c||!maintenance_enabled($cid)||(!maintenance_view_state($c,[])['ready']&&!($action==='service_start'&&maintenance_view_state($c,[])['service_start_ready'])))throw new InvalidArgumentException('Component is unavailable or maintenance support is not ready');
        maintenance_expire($cid);
        if(!in_array($action,['stop_game','stop_audio','leave_maintenance','service_start'],true)&&one("SELECT id FROM zp_commands WHERE component_id=? AND status IN ('requested','accepted') LIMIT 1",[$cid]))throw new InvalidArgumentException('Wait for the current command to finish, or use Stop game / Stop sound');
        $view=maintenance_view_state($c,maintenance_rows($cid));
        if(in_array($action,['laser_align','receiver_capture'],true)&&empty(maintenance_live($cid)['capabilities']['powered_calibration']))throw new InvalidArgumentException('Powered calibration requires controller bench-0.16.0 or later');
        if($action==='reboot_pi'&&empty(maintenance_live($cid)['reboot_supported']))throw new InvalidArgumentException('Install the optional Pi reboot permission first');
        if(in_array($action,MAINTENANCE_V2_ACTIONS,true)&&!$view['v2'])throw new InvalidArgumentException('Waiting for the updated controller status');
        if(in_array($action,array_merge(['audio_play','audio_mute','rgb_test','display_test','restart_game'],MAINTENANCE_V2_ACTIONS),true)&&!in_array($action,['service_start','start_lock'],true)&&!($view['enabled']&&$view['local_enabled']))throw new InvalidArgumentException('Tests are locked. Enter maintenance and press C on the exhibit keypad first.');
        $s=bin2hex(random_bytes(16));$id=substr($s,0,8).'-'.substr($s,8,4).'-'.substr($s,12,4).'-'.substr($s,16,4).'-'.substr($s,20);
        q("INSERT INTO zp_commands(id,component_id,requested_by,action,parameters,status,expires_at) VALUES (?,?,?,?,?,'requested',DATE_ADD(UTC_TIMESTAMP(),INTERVAL 60 SECOND))",[$id,$cid,$u['id'],$action,json_encode((object)$params,JSON_THROW_ON_ERROR)]);
        audit((int)$u['id'],'maintenance_requested',['component_id'=>$cid,'command_id'=>$id,'action'=>$action,'parameters'=>$params]);db()->commit();return $id;
    }catch(Throwable $e){if(db()->inTransaction())db()->rollBack();throw $e;}
}
function maintenance_rows(int $cid): array {
    maintenance_expire($cid);
    return q('SELECT id,action,status,result,created_at,updated_at,expires_at FROM zp_commands WHERE component_id=? ORDER BY created_at DESC,id DESC LIMIT 20',[$cid])->fetchAll();
}
function maintenance_result_label(?string $encoded): string {
    $r=json_decode($encoded ?? '{}',true);$label=str_replace('_',' ',is_string($r['reason'] ?? null)?$r['reason']:'');$inputs=$r['snapshot']['inputs'] ?? null;
    if(is_array($inputs)&&count($inputs)===3&&!array_filter($inputs,fn($v)=>!is_bool($v)))$label.=' · Beam 1 blocked: '.($inputs[0]?'yes':'no').' · Beam 2 blocked: '.($inputs[1]?'yes':'no').' · Objective input: '.($inputs[2]?'on':'off');
    return $label;
}
function maintenance_form(int $cid,string $action,string $label,string $fields='',bool $disabled=false): void {
    echo '<form data-maintenance-command="'.esc($action).'" class="maintenance-control" method="post" action="/maintenance.php">'.csrf_field().'<input type="hidden" name="component_id" value="'.$cid.'"><input type="hidden" name="command" value="'.esc($action).'"><h5>'.esc($label).'</h5><div class="maintenance-control-body">'.$fields.'</div><button'.($disabled?' disabled':'').'>'.esc($label).'</button></form>';
}
function maintenance_placeholder(string $label,string $detail): void {
    echo '<div class="maintenance-control maintenance-planned"><h5>'.esc($label).'</h5><div class="maintenance-control-body"><span class="maintenance-badge">Planned</span><p>'.esc($detail).'</p></div><button type="button" disabled aria-label="'.esc($label).' — planned">'.esc($label).'</button></div>';
}
function maintenance_group(string $title,string $description): void {
    echo '<section class="maintenance-group"><h4>'.esc($title).'</h4><p class="fine muted">'.esc($description).'</p><div class="maintenance-controls">';
}
function maintenance_group_end(): void {echo '</div></section>';}
function render_maintenance(array $e,array $cs,?array $viewer): void {
    if(($viewer['role'] ?? '')!=='admin')return;
    exhibit_section_start((int)$e['id'],'maintenance','Maintenance',false);
    echo '<link rel="stylesheet" href="/assets/maintenance.css"><p>Administrator controls · requests expire after 60 seconds. Command completion confirms software execution; speaker and light output remain physically unconfirmed.</p><p>Enter maintenance, then press <strong>C on the exhibit keypad</strong> to enable tests for five minutes. C renews that enable; D cancels tests and sound; B exits maintenance locally. Leaving maintenance returns to idle. Mute persists; unmute before returning to play if needed.</p>';
    if(isset($_SESSION['maintenance_notice'])){echo '<p class="alert" role="status">'.esc($_SESSION['maintenance_notice']).'</p>';unset($_SESSION['maintenance_notice']);}
    $found=false;
    foreach($cs as $c){$cid=(int)$c['id'];if(!$c['active']||!maintenance_enabled($cid))continue;$found=true;$ready=maintenance_ready($c);$m=dashboard_payload($c)['metrics'] ?? [];$rows=maintenance_rows($cid);$view=maintenance_view_state($c,$rows);$testLocked=!$ready||$view['pending']||!($view['enabled']&&$view['local_enabled']);$v2Locked=$testLocked||!$view['v2'];
        echo '<article class="card" data-maintenance-component="'.$cid.'"><h3>'.esc($c['name']).'</h3><p>'.($ready?'Component supports maintenance requests.':'Awaiting a fresh report from the maintenance-capable controller.').'</p><small>Reported mode: '.esc(str_replace('_',' ',$m['game_phase'] ?? 'unconfirmed')).' · Local test enable: '.(!empty($m['maintenance_local_enabled'])?'Reported enabled':'Not confirmed').'</small><div class="maintenance-mode" role="status" aria-live="polite">'.esc($view['label']).'</div><p class="maintenance-feedback" role="status" aria-live="polite"></p>';
        maintenance_group('Exhibit operation','Maintenance blocks new games. Exit returns the controller to idle; a new game still needs a local start.');
        maintenance_form($cid,'enter_maintenance','Enter maintenance','<p>Press local C after requesting entry.</p>',!$ready||$view['pending']);
        maintenance_form($cid,'leave_maintenance','Exit maintenance / return to idle','<p>Restore normal play readiness.</p>',!$ready);
        maintenance_form($cid,'stop_game','Stop game','<p>Stop the current game and its sound.</p>',!$ready);
        maintenance_form($cid,'start_lock','Disable new games','<input type="hidden" name="locked" value="1"><p>Let any current game finish; block later starts.</p>',!$ready||$view['pending']||!$view['v2']);
        maintenance_form($cid,'start_lock','Enable new games','<input type="hidden" name="locked" value="0"><p>Return to play readiness after leaving maintenance.</p>',!$ready||$view['pending']||!$view['v2']);
        maintenance_group_end();
        maintenance_group('Audio','Select known announcements, save playback level, mute or test the configured USB audio output.');
        $options='<label>Announcement<select name="clip">';foreach(MAINTENANCE_CLIPS as $v=>$label)$options.='<option value="'.esc($v).'">'.esc($label).'</option>';
        maintenance_form($cid,'audio_play','Play selected announcement',$options.'</select></label>',$testLocked);
        maintenance_form($cid,'stop_audio','Stop sound','<p>Cancel current narration and effects.</p>',!$ready);
        maintenance_form($cid,'audio_mute','Mute game audio','<input type="hidden" name="muted" value="1"><p>Mute is retained between games.</p>',$testLocked);
        maintenance_form($cid,'audio_mute','Unmute game audio','<input type="hidden" name="muted" value="0"><p>Restore announcements and effects.</p>',$testLocked);
        maintenance_form($cid,'audio_volume','Save playback level','<label>Playback level (%)<input name="percent" type="number" min="0" max="100" value="100" required></label><p>Relative to the configured amplifier/output level.</p>',$v2Locked);
        maintenance_form($cid,'audio_output_test','Test configured output','<p>Play the entrance clip through the configured USB audio output.</p>',$v2Locked);
        maintenance_group_end();
        $moduleLive=maintenance_live($cid);
        $moduleSupported=($moduleLive['capabilities']['module_count'] ?? null)===1&&!empty($moduleLive['capabilities']['powered_calibration']);
        maintenance_group('Laser modules','One HIGH/LOW wire controls each module’s laser and ring animation together. HIGH starts the Nano sequence and laser; LOW turns the laser off and lets the ring finish its shutdown animation.');
        echo '<div class="module-picker"><label>Selected laser module<select data-module-select><option value="1">Module 1</option></select></label><p class="fine muted" data-module-availability>'.($moduleSupported?'1 module configured. All modules currently means module 1.':'Waiting for fresh module capabilities.').'</p><p class="fine muted" data-module-state>Module command unconfirmed.</p></div>';
        $selected='<input type="hidden" name="scope" value="selected"><input type="hidden" name="module" value="1">';
        $all='<input type="hidden" name="scope" value="all"><input type="hidden" name="module" value="1">';
        maintenance_form($cid,'module_control','Selected module · HIGH / ON',$selected.'<input type="hidden" name="high" value="1"><p>Run the selected module for up to 30 seconds, then automatically send LOW.</p>',$v2Locked||!$moduleSupported);
        maintenance_form($cid,'module_control','Selected module · LOW / OFF',$selected.'<input type="hidden" name="high" value="0"><p>Cancel the active test and send LOW. The laser turns off; the ring finishes its shutdown effect.</p>',!$ready||!$moduleSupported);
        maintenance_form($cid,'module_control','All modules · HIGH / ON',$all.'<input type="hidden" name="high" value="1"><p>Run every configured module for up to 30 seconds, then automatically send LOW.</p>',$v2Locked||!$moduleSupported);
        maintenance_form($cid,'module_control','All modules · LOW / OFF',$all.'<input type="hidden" name="high" value="0"><p>Cancel active tests or gameplay and send LOW to every module output.</p>',!$ready);
        maintenance_group_end();
        maintenance_group('Entrance status light','This is separate from the laser-module rings. Test the entrance indicator color for five seconds.');
        $options='<label>Status-light color<select name="color">';foreach(['RED','GREEN','BLUE','YELLOW','PURPLE','OFF'] as $v)$options.='<option>'.esc($v).'</option>';
        maintenance_form($cid,'rgb_test','Test entrance status light',$options.'</select></label>',$testLocked);
        maintenance_group_end();
        maintenance_group('Laser alignment','Select the laser module to align with its matching receiver. The laser and ring share one HIGH/LOW command. Enter maintenance and press local C before testing.');
        echo '<div class="module-picker"><label>Laser module to align<select data-module-select><option value="1">Module 1 · receiver A0</option></select></label><p class="fine muted">Only module 1 is currently configured. This selection is shared with module controls and receiver calibration.</p></div>';
        $channel='<input type="hidden" name="module" value="1">';
        maintenance_form($cid,'laser_align','Align selected module · 30 seconds',$channel.'<p>Command the selected module ON for 30 seconds, then automatically OFF. Aim at receiver A0 and watch its reading below. Local D or Stop turns it off early.</p>',true);
        maintenance_form($cid,'stop_game','All module outputs OFF','<p>Cancel alignment, capture or gameplay and send LOW to the module.</p>',!$ready);
        maintenance_group_end();
        maintenance_group('Receiver calibration','TEMT6000 receiver 1 on Mega A0. Enter maintenance and press local C. Each capture powers the laser, waits for its output acknowledgment and 0.5-second settling, then records 100 fresh readings and turns it off. Keep the card in place for blocked captures; remove it for clear. Review all three before applying. Applying is acknowledged by the Mega and persists across restarts.');
        echo '<div class="module-picker"><label>Laser module to calibrate<select data-module-select><option value="1">Module 1 · receiver A0</option></select></label><p class="fine muted">Capture and apply calibration for the selected module and its matching receiver.</p></div>';
        echo '<div class="maintenance-live"><h5>Receiver 1 · live reading</h5><p data-live-receiver>Waiting for fresh receiver data…</p><p data-live-laser>Module command unconfirmed.</p><p data-live-calibration>No capture yet.</p><progress data-live-progress max="100" value="0"></progress><p data-live-settings></p><p data-live-diagnostics></p></div>';
        maintenance_form($cid,'receiver_capture','1 · Capture blocked beam',$channel.'<input type="hidden" name="phase" value="blocked"><p>Place an opaque card across the beam near the receiver, then capture 100 readings.</p>',$v2Locked);
        maintenance_form($cid,'receiver_capture','2 · Capture clear beam',$channel.'<input type="hidden" name="phase" value="clear"><p>Remove the card. Keep the beam steadily aimed at the receiver.</p>',$v2Locked);
        maintenance_form($cid,'receiver_capture','3 · Recheck blocked beam',$channel.'<input type="hidden" name="phase" value="blocked_check"><p>Block the same beam again to verify the ambient reading.</p>',$v2Locked);
        maintenance_form($cid,'receiver_apply','Apply proposed thresholds',$channel.'<input type="hidden" name="candidate_id" value=""><p>Enabled after three usable captures. Future games use the applied thresholds; no firmware upload needed.</p>',true);
        maintenance_form($cid,'receiver_thresholds','Save manual thresholds',$channel.'<label>Broken below<input name="break_below" type="number" min="1" max="1021" value="20" required></label><label>Clear above<input name="clear_above" type="number" min="2" max="1022" value="41" required></label><p>Keep the break threshold below the clear threshold.</p>',$v2Locked);
        maintenance_group_end();
        maintenance_group('Game settings','Save while maintenance is locally enabled. Values persist and apply to future games. The second beam remains a bench button.');
        $fields='';foreach(['duration'=>['Game duration (seconds)',10,3600,150],'startup'=>['Preparation (seconds)',1,30,5],'max_breaks'=>['Break limit',1,20,3],'cooldown'=>['Cooldown (seconds)',1,60,7],'warmup'=>['Recovery warmup (seconds)',1,30,5]] as $name=>[$label,$min,$max,$default])$fields.='<label>'.esc($label).'<input type="number" name="'.$name.'" min="'.$min.'" max="'.$max.'" value="'.$default.'" required></label>';
        $fields.='<fieldset><legend>Included channels</legend><label><input type="checkbox" name="beam1" value="1" checked> Beam 1 · A0 receiver</label><label><input type="checkbox" name="beam2" value="1" checked> Beam 2 · bench button</label></fieldset><fieldset><legend>Available modes</legend>';
        foreach(['usb'=>'Black Hat / Vexed · 16646#','usb-break-all'=>'Black Hat / Vexed accessible · 64661#','keys'=>'Corruption Reduction · 77004#','keys-break-all'=>'Corruption Reduction accessible · 40077#'] as $key=>$label)$fields.='<label><input type="checkbox" name="modes[]" value="'.$key.'" checked> '.esc($label).'</label>';
        maintenance_form($cid,'game_settings','Save game settings',$fields.'</fieldset>',$v2Locked);
        maintenance_group_end();
        maintenance_group('Hardware diagnostics','Live receiver, beam 2 button, objective, last keypad key, RC522 status and controller connection are shown above. Input snapshots are also retained in the command history.');
        maintenance_form($cid,'snapshot','Read input snapshot','<p>Read both beam inputs and the objective input.</p>',!$ready||$view['pending']);
        maintenance_form($cid,'display_test','Test display · 5 seconds','<p>Show 99:59, then restore the maintenance display.</p>',$testLocked);
        echo '<div class="maintenance-control"><h5>Keypad / objective / connection</h5><div class="maintenance-control-body"><p>Press keypad keys in maintenance and watch the live diagnostics above. C renews local enable, D cancels tests and B exits maintenance.</p></div></div>';
        maintenance_form($cid,'snapshot','RFID reader · check detection','<p>Reader health, scan count and entry state appear in live diagnostics above. Swipe a compatible 13.56 MHz tag while in maintenance to test detection without starting a game. No tag UID is stored.</p>',!$ready);


        maintenance_group_end();
        maintenance_group('Component services','Stop, restart and reinstall require locally enabled maintenance. Starting a stopped service returns to idle or maintenance; reboot requires the optional Pi permission.');
        maintenance_form($cid,'restart_game','Restart game program','<p>Restart the controller and return to maintenance.</p>',$testLocked);
        maintenance_form($cid,'service_stop','Stop game service','<p>Stop the controller process. This command worker stays available to start it again.</p>',$v2Locked);
        maintenance_form($cid,'service_start','Start game service','<p>Start the controller into idle or maintenance; does not start a game.</p>',!$view['service_start_ready']);
        maintenance_form($cid,'reboot_pi','Reboot Pi','<p>Needs the optional Pi permission installer. Connection is lost during reboot; completion waits for a changed boot ID.</p>',$v2Locked||empty(maintenance_live($cid)['reboot_supported']));
        maintenance_group_end();
        maintenance_group('Software','Installed versions, release history and administrator downloads remain in Equipment & components for this component.');
        echo '<div class="maintenance-control"><h5>Versions, releases & downloads</h5><div class="maintenance-control-body"><p>Open this exhibit’s component software records.</p></div><a class="maintenance-link" href="#exhibit-'.(int)$e['id'].'-equipment">Open component software</a></div>';
        maintenance_form($cid,'software_reinstall','Reinstall current archived release','<p>Reflash and verify the current Mega release using its existing immutable archive. The game returns to maintenance. Does not flash the Nanos.</p>',$v2Locked);
        maintenance_placeholder('Select a different archived release','Cross-version remote updates remain unavailable until migration and recovery checks are defined.');
        maintenance_group_end();
        maintenance_group('Future equipment','These controls remain planned until their actual hardware behavior is established.');
        maintenance_placeholder('Hazer diagnostics','Bounded output tests and device fault reporting.');
        maintenance_placeholder('Door / lock diagnostics','State sensing and deliberate tests after the required hardware behavior is defined.');
        maintenance_group_end();
        echo '<p class="fine muted">Output tests and setting changes require locally enabled maintenance, except the independent new-game lock and starting a stopped service. Module tests assert D9 for five seconds; physical laser switching is not connected. Restart returns to maintenance. Remote Stop is not a hardware emergency stop.</p><div class="table-wrap"><table class="maintenance-history" data-component="'.$cid.'"><thead><tr><th>Requested (UTC)</th><th>Action</th><th>Status</th><th>Result</th></tr></thead><tbody>';
        foreach($rows as $r)echo '<tr data-command="'.esc($r['id']).'"><td>'.esc($r['created_at']).'</td><td>'.esc(str_replace('_',' ',$r['action'])).'</td><td class="command-status">'.esc(ucfirst($r['status'])).'</td><td class="command-result">'.esc(maintenance_result_label($r['result'])).'</td></tr>';
        echo '</tbody></table></div><p class="fine muted">Latest 20 requests. Accepted means the Pi polled for the request, not that it completed. For Enter maintenance, Accepted can mean awaiting the local C press. Mode and request results refresh automatically.</p></article>';
    }
    if(!$found)echo '<p>No maintenance-enabled components for this exhibit yet.</p>';
    exhibit_section_end();echo '<script src="/assets/maintenance.js?v=20261102-alignment-selector-1" defer></script>';
}
