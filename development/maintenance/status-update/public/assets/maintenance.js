(() => {
  const cards = [...document.querySelectorAll('[data-maintenance-component]')];
  const protectedTests = ['audio_play','audio_mute','rgb_test','display_test','restart_game'];
  const escapeActions = ['stop_game','stop_audio','leave_maintenance'];
  function apply(card,state) {
    card.querySelector('.maintenance-mode').textContent=state.label;
    const summary=card.querySelector('small');if(summary)summary.textContent='Maintenance status updates automatically.';
    for(const form of card.querySelectorAll('form[data-maintenance-command]')) {
      const action=form.dataset.maintenanceCommand;
      form.querySelector('button').disabled=!state.ready || (state.pending&&!escapeActions.includes(action)) || (protectedTests.includes(action)&&!(state.enabled&&state.local_enabled));
    }
  }
  function history(card,commands) {
    const body=card.querySelector('.maintenance-history tbody');body.replaceChildren();
    for(const command of commands){
      let result={};try{result=command.result?JSON.parse(command.result):{};}catch{}
      let label=(result.reason||'').replaceAll('_',' ');const inputs=result.snapshot?.inputs;
      if(Array.isArray(inputs)&&inputs.length===3&&inputs.every(v=>typeof v==='boolean'))label+=' · Beam 1 blocked: '+(inputs[0]?'yes':'no')+' · Beam 2 blocked: '+(inputs[1]?'yes':'no')+' · Objective input: '+(inputs[2]?'on':'off');
      const row=document.createElement('tr');row.dataset.command=command.id;
      for(const value of [command.created_at,command.action.replaceAll('_',' '),command.status,label]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}body.append(row);
    }
  }
  async function update(card) {
    try{
      const response=await fetch('/maintenance.php?status='+encodeURIComponent(card.dataset.maintenanceComponent),{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw Error('status');const body=await response.json();apply(card,body.state);history(card,body.commands);
    }catch{apply(card,{ready:false,label:'Connection unconfirmed — unable to refresh maintenance status. Tests are locked.'});}
  }
  for(const card of cards){
    for(const form of card.querySelectorAll('form[data-maintenance-command]'))form.addEventListener('submit',async event=>{
      event.preventDefault();const feedback=card.querySelector('.maintenance-feedback');form.querySelector('button').disabled=true;feedback.textContent='Sending request…';
      try{
        const response=await fetch(form.action,{method:'POST',credentials:'same-origin',headers:{Accept:'application/json'},body:new FormData(form)});
        let body;try{body=await response.json();}catch{throw Error('Your session may have expired. Refresh the page and sign in again.');}
        feedback.textContent=body.error||body.message||'Request could not be sent.';
      }catch(error){feedback.textContent=error.message||'Unable to send request. Refresh status before retrying.';}
      await update(card);
    });
    update(card);
  }
  setInterval(()=>cards.forEach(update),3000);
})();
