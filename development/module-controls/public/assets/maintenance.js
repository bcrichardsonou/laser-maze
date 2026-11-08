(() => {
  const cards = [...document.querySelectorAll('[data-maintenance-component]')];
  const v2Actions=['receiver_capture','receiver_apply','receiver_thresholds','module_test','laser_align','game_settings','start_lock','audio_volume','audio_output_test','service_start','service_stop','reboot_pi','software_reinstall'];
  const protectedTests = ['audio_play','audio_mute','rgb_test','display_test','restart_game',...v2Actions];
  const escapeActions = ['stop_game','stop_audio','leave_maintenance'];
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
      const row=document.createElement('tr');row.dataset.command=command.id;
      for(const value of [command.created_at,command.action.replaceAll('_',' '),command.status,label]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}body.append(row);
    }
  }
  function livePanel(card,live,state) {
    const text=(selector,value)=>{const el=card.querySelector(selector);if(el)el.textContent=value;};
    const moduleForms=[...card.querySelectorAll('form[data-maintenance-command="module_control"]')];
    const supported=live?.capabilities?.module_count===1&&live?.capabilities?.powered_calibration===true;
    for(const form of moduleForms){
      const high=form.querySelector('[name="high"]').value==='1',scope=form.querySelector('[name="scope"]').value;
      if(high||scope==='selected')form.querySelector('button').disabled ||= !supported;
    }
    const selector=card.querySelector('[data-module-select]');if(selector)selector.disabled=!supported;
    text('[data-module-availability]',supported?'1 module configured. All modules currently means module 1.':'Module selection unavailable until a supported controller reports fresh capabilities.');
    text('[data-module-state]',live?`Module command: ${live.laser_command_on===true?'HIGH / ON':live.laser_command_on===false?'LOW / OFF':'unconfirmed'} · ${live.laser_seconds_remaining??0}s remaining. Physical output must be checked at the exhibit.`:'Module command unconfirmed.');
    if(!live){for(const form of card.querySelectorAll('form[data-maintenance-command="laser_align"],form[data-maintenance-command="receiver_capture"]'))form.querySelector('button').disabled=true;text('[data-live-laser]','Module command unconfirmed.');text('[data-live-receiver]','No fresh receiver data from the Pi. Check Pi power/network and the maintenance service. Saved capture values remain in command history below.');text('[data-live-diagnostics]','Connection/diagnostics unconfirmed.');return;}
    const reboot=card.querySelector('form[data-maintenance-command="reboot_pi"] button');if(reboot)reboot.disabled ||= !live.reboot_supported;
    for(const form of card.querySelectorAll('form[data-maintenance-command="laser_align"],form[data-maintenance-command="receiver_capture"]'))form.querySelector('button').disabled ||= !live.capabilities?.powered_calibration;
    text('[data-live-laser]',`Module command: ${live.laser_command_on===true?'HIGH / ON':live.laser_command_on===false?'LOW / OFF':'unconfirmed'} · ${live.laser_seconds_remaining??0}s remaining. Command state does not prove physical laser output.`);
    const r=live.receiver||{},t=r.thresholds||{},captures=r.captures||{},candidate=r.candidate;
    text('[data-live-receiver]',`A0: ${r.raw??'not sampled'} / 1023 · ${r.raw==null?'UNCONFIRMED':(r.blocked?'BLOCKED':'CLEAR')} · broken below ${t.break_below??'—'} / clear above ${t.clear_above??'—'}`);
    let summary=['blocked','clear','blocked_check'].map(k=>captures[k]?`${k.replaceAll('_',' ')}: median ${captures[k].median}, range ${captures[k].minimum}–${captures[k].maximum}`:`${k.replaceAll('_',' ')}: not captured`).join(' | ');
    if(candidate?.proposal)summary+=' · '+(candidate.proposal.usable?`Proposed: break ${candidate.proposal.proposed_break_threshold}, clear ${candidate.proposal.proposed_clear_threshold}`:candidate.proposal.reason);
    text('[data-live-calibration]',summary);
    const progress=card.querySelector('[data-live-progress]');if(progress){progress.value=live.capture_samples||0;progress.hidden=live.test!=='capture';}
    if(live.test==='capture')text('[data-live-calibration]',summary+` · Capturing ${live.capture_samples||0}/100 readings…`);
    const settings=live.settings||{};
    text('[data-live-settings]',`Current settings: ${settings.duration??'—'}s game, ${settings.startup??'—'}s preparation, ${settings.max_breaks??'—'} break limit, ${settings.cooldown??'—'}s cooldown. New games: ${live.play_locked?'DISABLED':'enabled'}.`);
    text('[data-live-diagnostics]',`Service: ${live.service_state??'unconfirmed'} · Controller: ${live.connected?'connected':'unconfirmed'} · Firmware ${live.firmware_version??'unconfirmed'} · Last key: ${live.last_key??'none'} · Beam 2: ${live.inputs?.[1]?'active':'released'} · Objective: ${live.inputs?.[2]?'ON':'OFF'} · Audio: ${live.audio?.output_device??'unconfirmed'} · RFID: ${live.rfid?.ready?'reader ready':'missing/unconfirmed'} · Tag responses: ${live.rfid?.diagnostics?.tag_responses??'—'} · Selection failures: ${live.rfid?.diagnostics?.selection_failures??'—'} · Scans this run: ${live.rfid?.scans_this_run??'—'} · Last scan: ${live.rfid?.seconds_since_scan==null?'none':live.rfid.seconds_since_scan+'s ago'} · Entry: ${(live.rfid?.entry?.state||'unconfirmed').replaceAll('_',' ')} (${live.rfid?.entry?.code_characters??0}/6 characters, ${live.rfid?.entry?.seconds_remaining??0}s)`);
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
    }catch(error){apply(card,{ready:false,label:'Connection unconfirmed — unable to refresh maintenance status. Tests are locked.'});const receiver=card.querySelector('[data-live-receiver]');if(receiver)receiver.textContent='Unable to refresh receiver readings. Reload this page; if it persists, check Pi connection.';console.error('Maintenance status refresh failed',error);}
  }
  for(const card of cards){
    card.querySelector('[data-module-select]')?.addEventListener('change',event=>{
      for(const field of card.querySelectorAll('form[data-maintenance-command="module_control"] [name="module"]'))field.value=event.target.value;
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
