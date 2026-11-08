(() => {
  const cards = [...document.querySelectorAll('[data-maintenance-component]')];
  const v2Actions=['rfid_start','rfid_end','rfid_reset','keypad_start','keypad_end','beams_check','receiver_auto','receiver_capture','receiver_apply','receiver_thresholds','module_test','laser_align','game_settings','start_lock','audio_volume','audio_output_test','service_start','service_stop','reboot_pi','software_reinstall','door_test'];
  function revealDiagnostic(){
    const target=document.getElementById(location.hash.slice(1));
    if(!target?.matches('.usb-test,.keypad-test,.rfid-test,.maintenance-group,.maintenance-diagnostic-links,.maintenance-history-heading'))return;
    const component=target.closest('[data-maintenance-component]');if(component)for(const link of component.querySelectorAll('.maintenance-diagnostic-links a')){if(link.hash===location.hash)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');}
    for(let parent=target.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;
    requestAnimationFrame(()=>target.scrollIntoView({block:'start'}));
  }
  addEventListener('hashchange',revealDiagnostic);revealDiagnostic();
  const protectedTests = ['audio_play','audio_mute','rgb_test','display_test','restart_game',...v2Actions];
  const escapeActions = ['stop_game','stop_audio','leave_maintenance','keypad_end','rfid_end','doors_release'];
  function apply(card,state) {
    card.querySelector('.maintenance-mode').textContent=state.label;
    const summary=card.querySelector('small');if(summary)summary.textContent='Maintenance status updates automatically.';
    for(const form of card.querySelectorAll('form[data-maintenance-command]')) {
      const action=form.dataset.maintenanceCommand;
      if(action==='module_control'){
        const high=form.querySelector('[name="high"]').value==='1';
        form.querySelector('button').disabled=!state.ready||(high&&(state.pending||!state.v2||!(state.enabled&&state.local_enabled)));
        continue;
      }
      form.querySelector('button').disabled=!state.ready || (state.pending&&!escapeActions.includes(action)) || (protectedTests.includes(action)&&!(state.enabled&&state.local_enabled)) || (v2Actions.includes(action)&&!state.v2);
      if(action==='start_lock')form.querySelector('button').disabled=!state.ready||state.pending||!state.v2;
      if(action==='keypad_end'||action==='rfid_end')form.querySelector('button').disabled=!state.ready;
      if(action==='service_start')form.querySelector('button').disabled=!state.service_start_ready;
    }
  }
  function history(card,commands) {
    const body=card.querySelector('.maintenance-history tbody');body.replaceChildren();
    for(const command of commands){
      let result={};try{result=typeof command.result==='string'?JSON.parse(command.result):(command.result||{});}catch{}
      let label=(result.reason||'').replaceAll('_',' ');const inputs=result.snapshot?.inputs;
      if(Array.isArray(inputs)&&inputs.length===3&&inputs.every(v=>typeof v==='boolean'))label+=' · Beam 1 blocked: '+(inputs[0]?'yes':'no')+' · Beam 2 blocked: '+(inputs[1]?'yes':'no')+' · Objective input: '+(inputs[2]?'on':'off');
      if(result.snapshot?.rfid)label+=` · RFID: ${result.snapshot.rfid.ready?'ready':'missing'} · Scans: ${result.snapshot.rfid.scans_this_run} · Entry: ${(result.snapshot.rfid.entry_state||'unknown').replaceAll('_',' ')}`;
      const receiver=result.snapshot?.receiver;
      if(receiver){
        if(Number.isFinite(receiver.raw))label+=` · A0 snapshot: ${receiver.raw}/1023`;
        for(const phase of ['blocked','clear','blocked_check']){const sample=receiver.captures?.[phase];if(sample)label+=` · ${phase.replaceAll('_',' ')}: median ${sample.median}, range ${sample.minimum}–${sample.maximum} (${sample.count} readings)`;}
      }
      if(result.snapshot?.beam_check?.command_id===command.id)for(const module of result.snapshot.beam_check.modules||[])label+=` · Module ${module.module}: ${(module.state||'unconfirmed').replaceAll('_',' ')}`;
      const row=document.createElement('tr');row.dataset.command=command.id;
      for(const value of [command.created_at,command.action.replaceAll('_',' '),command.status,label]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}body.append(row);
    }
  }
  function livePanel(card,live,state) {
    const text=(selector,value)=>{const el=card.querySelector(selector);if(el)el.textContent=value;};
    const keyValid=live&&live.connected===true,session=live?.keypad_test;
    const keyActive=keyValid&&session?.status==='running';
    const key=session?.last_key;
    text('[data-keypad-value]',keyValid&&key?key:'—');
    text('[data-keypad-time]',!keyValid?'Controller connection unconfirmed.':key?'Received '+new Date(session.last_key_at*1000).toLocaleTimeString()+' · press '+session.press_count:keyActive?'Waiting for your first test key…':'Start keypad test to read keys here.');
    text('[data-keypad-seen]',keyValid?'Keys detected: '+(session?.seen?.length?session.seen.join('  '):'none')+'.':'Keys cannot be confirmed while disconnected.');
    let keypadStatus=!keyValid?'Connection lost — test state unconfirmed. The Pi ends the test automatically.':keyActive?'TEST ACTIVE · '+Math.max(0,session.ends_at-(live.sampled_at||Math.floor(Date.now()/1000)))+' seconds remaining · all keypad shortcuts disabled.':session?'TEST ENDED · normal shortcuts restored after releasing held keys.':'Test not started. Press Start keypad test after local maintenance confirmation.';
    text('[data-keypad-status]',keypadStatus);
    const keyCard=card.querySelector('.keypad-test');if(keyCard)keyCard.dataset.active=keyActive?'true':'false';
    for(const form of card.querySelectorAll('form[data-maintenance-command]')){
      const action=form.dataset.maintenanceCommand;
      if(keyActive&&!['keypad_end','stop_game','stop_audio','leave_maintenance','snapshot','doors_release'].includes(action))form.querySelector('button').disabled=true;
      if(action==='keypad_start')form.querySelector('button').disabled ||= !keyValid||!live.capabilities?.isolated_keypad_test;
      if(action==='keypad_end')form.querySelector('button').disabled ||= !keyActive||!live.capabilities?.isolated_keypad_test;
    }
    const rfid=live?.rfid,rfidSession=live?.rfid_test;
    const rfidActive=keyValid&&rfidSession?.status==='running';
    const readerReady=keyValid&&rfid?.ready===true;
    text('[data-rfid-health]',!keyValid?'Reader connection unconfirmed — no fresh Pi report.':readerReady?'READER CONNECTED · ready to scan.':'READER MISSING / NOT READY · check the USB cable and hub; then Reconnect reader. '+(rfid?.diagnostics?.error||''));
    text('[data-rfid-test-status]',!keyValid?'Test state unconfirmed. The Pi ends active tests automatically.':rfidActive?'TEST ACTIVE · '+Math.max(0,rfidSession.ends_at-(live.sampled_at||Math.floor(Date.now()/1000)))+' seconds remaining · scans cannot start a game.':rfidSession?'TEST ENDED · results from the last test are shown below.':'Test not started. Choose Start RFID test after local maintenance confirmation.');
    text('[data-rfid-test-count]',keyValid&&rfidSession?String(rfidSession.scans):'—');
    text('[data-rfid-last-scan]',!keyValid?'Scan feedback unconfirmed.':rfidSession?.last_scan_at?'CARD READ · '+new Date(rfidSession.last_scan_at*1000).toLocaleString():rfidActive?'Waiting for a card. Present it near the reader, then lift it away.':'No test scan yet.');
    text('[data-rfid-test-detail]',!keyValid?'Check the Pi connection before interpreting any earlier result.':rfidSession?(rfidSession.scans===0&&rfidSession.selection_failures>0?'Tag signal detected, but the card could not be read. Try a known working card. ':'')+`Tag responses: ${rfidSession.tag_responses??0} · Unsuccessful reads: ${rfidSession.selection_failures??0}.`:'The two-minute test starts with a fresh scan count.');
    const rfidCard=card.querySelector('.rfid-test');if(rfidCard)rfidCard.dataset.active=rfidActive?'true':'false';
    for(const form of card.querySelectorAll('form[data-maintenance-command]')){
      const action=form.dataset.maintenanceCommand;
      if(rfidActive&&!['rfid_end','rfid_reset','stop_game','stop_audio','leave_maintenance','snapshot','doors_release'].includes(action))form.querySelector('button').disabled=true;
      if(['rfid_start','rfid_reset'].includes(action))form.querySelector('button').disabled ||= !keyValid||!live.capabilities?.rfid_test;
      if(action==='rfid_end')form.querySelector('button').disabled ||= !rfidActive||!live.capabilities?.rfid_test;
    }
    const doors=live?.doors;
    text('[data-door-state]',!keyValid||!doors?.commanded?'Relay commands unconfirmed.':`Entry: ${doors.commanded[0]?'LOCK commanded':'UNLOCK commanded'} · Exit: ${doors.commanded[1]?'LOCK commanded':'UNLOCK commanded'}. ${doors.exit_release_seconds>0?` Exit window: ${doors.exit_release_seconds}s remaining.`:""} Door position and independent release state are not sensed.`);
    for(const f of card.querySelectorAll('form[data-maintenance-command="door_test"],form[data-maintenance-command="doors_release"]'))f.querySelector('button').disabled ||= !keyValid||!live.capabilities?.door;
    const usb=live?.usb_input;
    text('[data-usb-state]',!keyValid?'USB INPUT UNCONFIRMED · Pi connection unavailable.':!usb?.configured?'USB SOCKET NOT CONFIGURED':usb.error||usb.present==null?'USB INPUT UNCONFIRMED · check the configured connection.':usb.present?'USB DRIVE INSERTED':'USB SOCKET EMPTY');
    text('[data-usb-detail]',keyValid&&usb?`Insertions detected: ${usb.insertions_this_run||0} · Removals detected: ${usb.removals_this_run||0} (since the game program started).`:'Waiting for fresh USB input data.');
    text('[data-usb-updated]',keyValid&&usb?'Updated '+new Date(live.sampled_at*1000).toLocaleTimeString()+'. Refreshes automatically; only the visitor socket is monitored.':'USB state cannot be confirmed until the Pi reports fresh data.');
    const moduleForms=[...card.querySelectorAll('form[data-maintenance-command="module_control"]')];
    const supported=live?.capabilities?.module_count===1&&live?.capabilities?.powered_calibration===true;
    for(const form of moduleForms){
      const high=form.querySelector('[name="high"]').value==='1',scope=form.querySelector('[name="scope"]').value;
      if(high||scope==='selected')form.querySelector('button').disabled ||= !supported;
    }
    for(const selector of card.querySelectorAll('[data-module-select]'))selector.disabled=!supported;
    text('[data-module-availability]',supported?'1 module configured. All modules currently means module 1.':'Module selection unavailable until a supported controller reports fresh capabilities.');
    text('[data-module-state]',live?`Module command: ${live.laser_command_on===true?'HIGH / ON':live.laser_command_on===false?'LOW / OFF':'unconfirmed'} · ${live.laser_seconds_remaining??0}s remaining. Physical output must be checked at the exhibit.`:'Module command unconfirmed.');
    const beamButton=card.querySelector('form[data-maintenance-command="beams_check"] button');
    if(beamButton)beamButton.disabled ||= !supported||live?.capabilities?.all_beams_check!==true;
    const beamList=card.querySelector('[data-beam-check-modules]');if(beamList)beamList.replaceChildren();
    const check=live?.beam_check;
    let beamSummary='No beam test yet. Keep the paths clear before testing.';
    if(!live)beamSummary='No fresh controller connection. Beam test results are unconfirmed.';
    else if(live.test==='beams')beamSummary=live.beam_check_step==='off'?'Readings collected. Turning all modules OFF and waiting for controller confirmation.':`Testing all enabled beams · ${live.capture_samples||0}/100 readings. Keep paths clear; allow startup to finish.`;
    else if(check){
      const when=check.finished_at?' · '+new Date(check.finished_at*1000).toLocaleString():'';
      if(check.status==='completed')beamSummary=check.tested_count===0?'No enabled laser receivers to test.':(check.all_clear?`All ${check.tested_count} enabled beam${check.tested_count===1?'':'s'} clear.`:'Beam check needs attention. See module results below.');
      else beamSummary='Beam test '+(check.status==='cancelled'?'cancelled':'unconfirmed')+'. No all-clear result.';
      beamSummary+=when;
      if(beamList)for(const module of check.modules||[]){const item=document.createElement('li');const labels={clear:'CLEAR',not_detected:'BEAM NOT DETECTED',unstable:'UNSTABLE — reading crossed the clear threshold',disabled:'DISABLED — not tested'};item.textContent=`Module ${module.module} · ${module.pin}: ${labels[module.state]||'UNCONFIRMED'}`+(Number.isFinite(module.minimum)?` · reading ${module.minimum}–${module.maximum}; clear at ${module.clear_above} or above`:'');beamList.append(item);}
    }
    text('[data-beam-check-summary]',beamSummary);
    if(!live){for(const form of card.querySelectorAll('form[data-maintenance-command="laser_align"],form[data-maintenance-command="receiver_auto"],form[data-maintenance-command="receiver_capture"],form[data-maintenance-command="receiver_apply"],form[data-maintenance-command="receiver_thresholds"]'))form.querySelector('button').disabled=true;text('[data-live-laser]','Module command unconfirmed.');text('[data-live-receiver]','No fresh receiver data from the Pi. Check Pi power/network and the maintenance service. Saved capture values remain in command history below.');text('[data-live-diagnostics]','Connection/diagnostics unconfirmed.');return;}
    const automatic=card.querySelector('form[data-maintenance-command="receiver_auto"] button');if(automatic)automatic.disabled ||= !live.capabilities?.automatic_calibration;
    const reboot=card.querySelector('form[data-maintenance-command="reboot_pi"] button');if(reboot)reboot.disabled ||= !live.reboot_supported;
    for(const form of card.querySelectorAll('form[data-maintenance-command="laser_align"],form[data-maintenance-command="receiver_auto"],form[data-maintenance-command="receiver_capture"],form[data-maintenance-command="receiver_apply"],form[data-maintenance-command="receiver_thresholds"]'))form.querySelector('button').disabled ||= !supported;
    text('[data-live-laser]',`Module command: ${live.laser_command_on===true?'HIGH / ON':live.laser_command_on===false?'LOW / OFF':'unconfirmed'} · ${live.laser_seconds_remaining??0}s remaining. Command state does not prove physical laser output.`);
    const r=live.receiver||{},t=r.thresholds||{},captures=r.captures||{},candidate=r.candidate;
    text('[data-live-receiver]',`A0: ${r.raw??'not sampled'} / 1023 · ${r.raw==null?'UNCONFIRMED':(r.blocked?'BLOCKED':'CLEAR')} · broken below ${t.break_below??'—'} / clear above ${t.clear_above??'—'}`);
    const stepNames={blocked:'1 of 3 · Measuring laser OFF background',clear:'2 of 3 · Measuring laser ON',blocked_check:'3 of 3 · Rechecking laser OFF',saving:'Saving and waiting for controller confirmation'};
    let summary='Ready to calibrate. Aim the laser and keep the beam path clear.';
    if(candidate?.mode==='automatic_off_on_off'){
      if(candidate.applied)summary=`Calibration saved automatically. Broken below ${t.break_below}; clear above ${t.clear_above}.`;
      else if(!candidate.proposal?.usable)summary='Calibration not saved. '+candidate.proposal.reason+' Existing thresholds are unchanged.';
      else summary='Measurements passed. Waiting for saved-threshold confirmation.';
    }
    if(live.test==='auto')summary=(stepNames[live.calibration_step]||'Calibrating')+` · ${live.capture_samples||0}/100 readings. Keep the beam path clear.`;
    if(live.calibration_step==='saving')summary=stepNames.saving;
    text('[data-live-calibration]',summary);
    const progress=card.querySelector('[data-live-progress]');if(progress){progress.value=live.capture_samples||0;progress.hidden=live.test!=='auto';}
    const settings=live.settings||{};
    text('[data-live-settings]',`Current settings: ${settings.duration??'—'}s game, ${settings.startup??'—'}s preparation, ${settings.max_breaks??'—'} break limit, ${settings.cooldown??'—'}s cooldown. New games: ${live.play_locked?'DISABLED':'enabled'}.`);
    text('[data-live-diagnostics]',`Service: ${live.service_state??'unconfirmed'} · Controller: ${live.connected?'connected':'unconfirmed'} · Firmware ${live.firmware_version??'unconfirmed'} · Beam 2: ${live.inputs?.[1]?'active':'released'} · Audio: ${live.audio?.output_device??'unconfirmed'} · RFID: ${live.rfid?.ready?'reader ready':'missing/unconfirmed'} · Tag responses: ${live.rfid?.diagnostics?.tag_responses??'—'} · Selection failures: ${live.rfid?.diagnostics?.selection_failures??'—'} · Scans this run: ${live.rfid?.scans_this_run??'—'} · Last scan: ${live.rfid?.seconds_since_scan==null?'none':live.rfid.seconds_since_scan+'s ago'} · Entry: ${(live.rfid?.entry?.state||'unconfirmed').replaceAll('_',' ')} (${live.rfid?.entry?.code_characters??0}/6 characters, ${live.rfid?.entry?.seconds_remaining??0}s)`);
    const applyForm=card.querySelector('form[data-maintenance-command="receiver_apply"]');
    if(applyForm){applyForm.querySelector('[name="candidate_id"]').value=candidate?.id||'';applyForm.querySelector('button').disabled ||= !candidate?.proposal?.usable || Date.now()/1000-(candidate?.created_at||0)>1800;}
    for(const form of card.querySelectorAll('form[data-maintenance-command="receiver_capture"]')){
      const phase=form.querySelector('[name="phase"]').value;
      form.querySelector('button').disabled ||= phase==='clear'&&!captures.blocked || phase==='blocked_check'&&!(captures.blocked&&captures.clear);
    }
    for(const form of card.querySelectorAll('form[data-maintenance-command]')){
      if(form.dataset.edited)continue;
      const set=(name,value)=>{const field=form.querySelector(`[name="${name}"]`);if(field&&value!==undefined)field.value=value;};
      if(form.dataset.maintenanceCommand==='receiver_thresholds'){set('break_below',t.break_below);set('clear_above',t.clear_above);}
      if(form.dataset.maintenanceCommand==='audio_volume')set('percent',live.audio?.volume);
      if(form.dataset.maintenanceCommand==='game_settings'){
        for(const key of ['duration','startup','cooldown','warmup','max_breaks'])set(key,settings[key]);
        for(let i=1;i<=2;i++){const field=form.querySelector(`[name="beam${i}"]`);if(field&&settings.enabled_beams)field.checked=!!settings.enabled_beams[i-1];}
        for(const field of form.querySelectorAll('[name="modes[]"]'))if(settings.available_modes)field.checked=settings.available_modes.includes(field.value);
      }
    }
  }
  async function update(card) {
    try{
      const response=await fetch('/maintenance.php?status='+encodeURIComponent(card.dataset.maintenanceComponent),{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw Error('status');const body=await response.json();apply(card,body.state);history(card,body.commands);livePanel(card,body.live,body.state);
    }catch(error){apply(card,{ready:false,label:'Connection unconfirmed — unable to refresh maintenance status. Tests are locked.'});for(const [selector,value] of [['[data-usb-updated]','USB state unconfirmed — unable to refresh.'],['[data-usb-state]','USB INPUT UNCONFIRMED · unable to refresh status.'],['[data-usb-detail]','Earlier readings are unconfirmed.'],['[data-rfid-health]','Reader connection unconfirmed.'],['[data-rfid-test-status]','Unable to refresh RFID test feedback.'],['[data-rfid-test-count]','—'],['[data-rfid-last-scan]','Scan feedback unconfirmed.'],['[data-rfid-test-detail]','Check the Pi connection.'],['[data-keypad-value]','—'],['[data-keypad-time]','Last key cannot be confirmed while disconnected.'],['[data-keypad-seen]','Keys cannot be confirmed while disconnected.'],['[data-keypad-status]','Unable to refresh keypad feedback. Check the Pi connection; do not treat an old result as a new key press.']]){const node=card.querySelector(selector);if(node)node.textContent=value;}const keyCard=card.querySelector('.keypad-test');if(keyCard)keyCard.dataset.active='false';const rfidCard=card.querySelector('.rfid-test');if(rfidCard)rfidCard.dataset.active='false';const receiver=card.querySelector('[data-live-receiver]');if(receiver)receiver.textContent='Unable to refresh receiver readings. Reload this page; if it persists, check Pi connection.';console.error('Maintenance status refresh failed',error);}
  }
  for(const card of cards){
    for(const selector of card.querySelectorAll('[data-module-select]'))selector.addEventListener('change',event=>{
      for(const other of card.querySelectorAll('[data-module-select]'))other.value=event.target.value;
      for(const field of card.querySelectorAll('form[data-maintenance-command] [name="module"]'))field.value=event.target.value;
    });
    for(const form of card.querySelectorAll('form[data-maintenance-command]')){form.addEventListener('input',()=>{form.dataset.edited='1';});form.addEventListener('change',()=>{form.dataset.edited='1';});form.addEventListener('submit',async event=>{
      event.preventDefault();const feedback=card.querySelector('.maintenance-feedback');form.querySelector('button').disabled=true;feedback.textContent='Sending request…';
      try{
        const response=await fetch(form.action,{method:'POST',credentials:'same-origin',headers:{Accept:'application/json'},body:new FormData(form)});
        let body;try{body=await response.json();}catch{throw Error('Your session may have expired. Refresh the page and sign in again.');}
        feedback.textContent=body.error||body.message||'Request could not be sent.';
      }catch(error){feedback.textContent=error.message||'Unable to send request. Refresh status before retrying.';}
      await update(card);
    });}
    update(card);
  }
  setInterval(()=>cards.forEach(update),3000);
})();
