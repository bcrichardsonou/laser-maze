<?php
const MAINTENANCE_ACTIONS=['enter_maintenance','leave_maintenance','stop_game','snapshot','audio_play','stop_audio','audio_mute','rgb_test','display_test','restart_game'];
const MAINTENANCE_CLIPS=['preparation'=>'Preparation','entrance'=>'Entrance','warning90'=>'90-second warning','warning30'=>'30-second warning','warning10'=>'10-second warning','beam'=>'Beam alarm','win_keys'=>'Key objective win','win_usb'=>'USB objective win','beam_loss'=>'Beam-limit loss','timeout'=>'Time up'];
function maintenance_parameters(string $action,array $p): array {
    if(!in_array($action,MAINTENANCE_ACTIONS,true))throw new InvalidArgumentException('Unsupported maintenance action');
    if($action==='audio_play'){if(array_keys($p)!==['clip']||!is_string($p['clip'])||!isset(MAINTENANCE_CLIPS[$p['clip']]))throw new InvalidArgumentException('Choose a known audio clip');return $p;}
    if($action==='audio_mute'){if(array_keys($p)!==['muted']||!is_bool($p['muted']))throw new InvalidArgumentException('Invalid mute setting');return $p;}
    if($action==='rgb_test'){if(array_keys($p)!==['color']||!in_array($p['color'],['RED','GREEN','BLUE','YELLOW','PURPLE','OFF'],true))throw new InvalidArgumentException('Choose a supported color');return $p;}
    if($p)throw new InvalidArgumentException('Unexpected command parameters');return [];
}
function maintenance_enabled(int $cid): bool {return (one('SELECT value FROM zp_settings WHERE name=?',['maintenance_component:'.$cid])['value'] ?? '')==='1';}
function maintenance_ready(array $c): bool {
    return $c['active'] && fresh($c) && $c['state_at'] && time()-(new DateTimeImmutable($c['state_at'],new DateTimeZone('UTC')))->getTimestamp()<=120 && (dashboard_payload($c)['metrics']['maintenance_protocol'] ?? null)===1;
}
function maintenance_expire(int $cid): void {
    q("UPDATE zp_commands SET status=CASE WHEN status='requested' THEN 'expired' ELSE 'unconfirmed' END,updated_at=UTC_TIMESTAMP() WHERE component_id=? AND status IN ('requested','accepted') AND expires_at<=UTC_TIMESTAMP()",[$cid]);
}
function maintenance_enqueue(array $u,int $cid,string $action,array $params): string {
    if(($u['role'] ?? '')!=='admin')throw new InvalidArgumentException('Administrator access required');
    $params=maintenance_parameters($action,$params);
    db()->beginTransaction();
    try {
        $c=one('SELECT * FROM zp_components WHERE id=? FOR UPDATE',[$cid]);
        if(!$c||!maintenance_enabled($cid)||!maintenance_ready($c))throw new InvalidArgumentException('Component is unavailable or maintenance support is not ready');
        maintenance_expire($cid);
        if(!in_array($action,['stop_game','stop_audio'],true)&&one("SELECT id FROM zp_commands WHERE component_id=? AND status IN ('requested','accepted') LIMIT 1",[$cid]))throw new InvalidArgumentException('Wait for the current command to finish, or use Stop game / Stop sound');
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
    echo '<form class="maintenance-control" method="post" action="/maintenance.php">'.csrf_field().'<input type="hidden" name="component_id" value="'.$cid.'"><input type="hidden" name="command" value="'.esc($action).'"><h5>'.esc($label).'</h5><div class="maintenance-control-body">'.$fields.'</div><button'.($disabled?' disabled':'').'>'.esc($label).'</button></form>';
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
    $found=false;
    foreach($cs as $c){$cid=(int)$c['id'];if(!$c['active']||!maintenance_enabled($cid))continue;$found=true;$ready=maintenance_ready($c);$m=dashboard_payload($c)['metrics'] ?? [];
        echo '<article class="card"><h3>'.esc($c['name']).'</h3><p>'.($ready?'Component supports maintenance requests.':'Awaiting a fresh report from the maintenance-capable controller.').'</p><small>Reported mode: '.esc(str_replace('_',' ',$m['game_phase'] ?? 'unconfirmed')).' · Local test enable: '.(!empty($m['maintenance_local_enabled'])?'Reported enabled':'Not confirmed').'</small>';
        maintenance_group('Exhibit operation','Maintenance blocks new games. Exit returns the controller to idle; a new game still needs a local start.');
        maintenance_form($cid,'enter_maintenance','Enter maintenance','<p>Press local C after requesting entry.</p>',!$ready);
        maintenance_form($cid,'leave_maintenance','Exit maintenance / return to idle','<p>Restore normal play readiness.</p>',!$ready);
        maintenance_form($cid,'stop_game','Stop game','<p>Stop the current game and its sound.</p>',!$ready);
        maintenance_placeholder('Disable / enable new games','Independent play lock, outside maintenance mode.');
        maintenance_group_end();
        maintenance_group('Audio','Existing announcements and mute are available. New audio settings are shown below as planned.');
        $options='<label>Announcement<select name="clip">';foreach(MAINTENANCE_CLIPS as $v=>$label)$options.='<option value="'.esc($v).'">'.esc($label).'</option>';
        maintenance_form($cid,'audio_play','Play selected announcement',$options.'</select></label>',!$ready);
        maintenance_form($cid,'stop_audio','Stop sound','<p>Cancel current narration and effects.</p>',!$ready);
        maintenance_form($cid,'audio_mute','Mute game audio','<input type="hidden" name="muted" value="1"><p>Mute is retained between games.</p>',!$ready);
        maintenance_form($cid,'audio_mute','Unmute game audio','<input type="hidden" name="muted" value="0"><p>Restore announcements and effects.</p>',!$ready);
        maintenance_placeholder('Set volume','Adjust and save the exhibit playback level.');
        maintenance_placeholder('Test output device','Identify the configured audio adapter and play a dedicated test cue.');
        maintenance_group_end();
        maintenance_group('LED rings','The current prototype has one RGB LED. Fifteen independently controlled eight-LED rings are planned.');
        $options='<label>Bench RGB color<select name="color">';foreach(['RED','GREEN','BLUE','YELLOW','PURPLE','OFF'] as $v)$options.='<option>'.esc($v).'</option>';
        maintenance_form($cid,'rgb_test','Test bench RGB · 5 seconds',$options.'</select></label>',!$ready);
        maintenance_placeholder('Select module / ring color','Choose one ring or all rings and a color.');
        maintenance_placeholder('Set ring brightness','Set and save brightness for the selected ring.');
        maintenance_placeholder('Test ring animation','Choose an animation for a bounded test.');
        maintenance_placeholder('All ring lights off','Clear all ring outputs; bench OFF is available in the color selector.');
        maintenance_group_end();
        maintenance_group('Laser alignment','Planned controls become available after the real laser drivers, channel mapping and automatic shutoff are verified.');
        maintenance_placeholder('Select laser','Choose a numbered laser and show its matching receiver.');
        maintenance_placeholder('Timed alignment test','Turn the selected laser on for a limited alignment period.');
        maintenance_placeholder('All lasers on · timed alignment','Enable all lasers for alignment, with a visible countdown and automatic shutoff.');
        maintenance_placeholder('Selected laser off','Turn off the selected laser output.');
        maintenance_placeholder('All lasers off','Turn off every laser output.');
        maintenance_group_end();
        maintenance_group('Receiver calibration','Analog receiver reporting and calibration have not yet been added to the controller.');
        maintenance_placeholder('Live light readings','Show each receiver value, beam state and alignment quality.');
        maintenance_placeholder('Capture laser-on level','Record the illuminated baseline for the selected receiver.');
        maintenance_placeholder('Capture laser-off level','Record the ambient baseline with the laser off.');
        maintenance_placeholder('Set receiver thresholds','Review and save break/clear thresholds and hysteresis.');
        maintenance_placeholder('Identify weak alignment','Flag receivers with a small on/off margin or unstable readings.');
        maintenance_group_end();
        maintenance_group('Game settings','Current rules remain in use. Editable settings will be validated and applied between games.');
        foreach(['Game duration'=>'Set the running timer.','Startup delay'=>'Set the preparation period.','Beam-break limit'=>'Set the normal-mode failure limit.','Cooldown'=>'Set the pause between games.','Enabled beams'=>'Choose the beams included in a game.','Available modes'=>'Enable or disable the supported game modes.'] as $label=>$detail)maintenance_placeholder($label,$detail);
        maintenance_group_end();
        maintenance_group('Hardware diagnostics','The snapshot reads both bench beam buttons and the objective input. A dedicated live diagnostic panel is planned.');
        maintenance_form($cid,'snapshot','Read input snapshot','<p>Read both beam inputs and the objective input.</p>',!$ready);
        maintenance_form($cid,'display_test','Test display · 5 seconds','<p>Show 99:59, then restore the maintenance display.</p>',!$ready);
        maintenance_placeholder('Test keypad','Show the last key and verify each keypad position.');
        maintenance_placeholder('Test RFID reader','Show tag detection after the separate RFID reader is connected.');
        maintenance_placeholder('Live objective inputs','Show objective transitions and their current states.');
        maintenance_placeholder('Arduino connection diagnostics','Show handshake, firmware version, connection status and recovery history.');
        maintenance_group_end();
        maintenance_group('Component services','Restart requires locally enabled maintenance. Additional service controls are planned.');
        maintenance_form($cid,'restart_game','Restart game program','<p>Restart the controller and return to maintenance.</p>',!$ready);
        maintenance_placeholder('Start / stop game service','Manage the controller service and show its resulting state.');
        maintenance_placeholder('Reboot Pi','Request a deliberate reboot and track reconnection.');
        maintenance_group_end();
        maintenance_group('Software','Installed versions, release history and administrator downloads remain in Equipment & components for this component.');
        echo '<div class="maintenance-control"><h5>Versions, releases & downloads</h5><div class="maintenance-control-body"><p>Open this exhibit’s component software records.</p></div><a class="maintenance-link" href="#exhibit-'.(int)$e['id'].'-equipment">Open component software</a></div>';
        maintenance_placeholder('Controlled update / reinstall','Select an archived release and verify a managed deployment.');
        maintenance_group_end();
        maintenance_group('Future equipment','These controls remain planned until their actual hardware behavior is established.');
        maintenance_placeholder('Hazer diagnostics','Bounded output tests and device fault reporting.');
        maintenance_placeholder('Door / lock diagnostics','State sensing and deliberate tests after the required hardware behavior is defined.');
        maintenance_group_end();
        echo '<p class="fine muted">Light/display tests require locally enabled maintenance. Beam/laser outputs stay off. Restart also requires local enable and returns to maintenance. Remote Stop is not a hardware emergency stop.</p><div class="table-wrap"><table class="maintenance-history" data-component="'.$cid.'"><thead><tr><th>Requested (UTC)</th><th>Action</th><th>Status</th><th>Result</th></tr></thead><tbody>';
        foreach(maintenance_rows($cid) as $r)echo '<tr data-command="'.esc($r['id']).'"><td>'.esc($r['created_at']).'</td><td>'.esc(str_replace('_',' ',$r['action'])).'</td><td class="command-status">'.esc(ucfirst($r['status'])).'</td><td class="command-result">'.esc(maintenance_result_label($r['result'])).'</td></tr>';
        echo '</tbody></table></div><p class="fine muted">Latest 20 requests. Accepted means the Pi polled for the request, not that it completed. For Enter maintenance, Accepted can mean awaiting the local C press. Refresh the page for the newest reported mode.</p></article>';
    }
    if(!$found)echo '<p>No maintenance-enabled components for this exhibit yet.</p>';
    exhibit_section_end();echo '<script src="/assets/maintenance.js" defer></script>';
}
