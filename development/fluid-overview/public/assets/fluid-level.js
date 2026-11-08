(() => {
  if(window.zocoFluidLevelLoaded)return;window.zocoFluidLevelLoaded=true;
  const token=new URL(location.href).searchParams.get('token');
  const labels={reading:'Live reading',unconfirmed:'Unconfirmed',uncalibrated:'Calibration needed',check_sensor:'Check sensor'};
  for(const card of document.querySelectorAll('[data-fluid-component]')){
    let busy=false;
    function display(p){
      const fresh=Number.isInteger(p?.updated_at)&&Math.abs(Date.now()/1000-p.updated_at)<=12;
      const known=fresh&&p.state==='reading'&&Number.isFinite(p.percent)&&p.percent>=0&&p.percent<=100;
      const state=known?'reading':fresh&&['uncalibrated','check_sensor'].includes(p?.state)?p.state:'unconfirmed';
      card.dataset.fluidState=state;card.querySelector('[data-fluid-status]').textContent=labels[state];
      card.querySelector('[data-fluid-percent]').textContent=known?p.percent.toLocaleString(undefined,{maximumFractionDigits:1})+'%':'—';
      card.querySelector('[data-fluid-fill]').style.height=(known?p.percent:0)+'%';
      const meter=card.querySelector('[role="meter"]');
      if(known){meter.setAttribute('aria-valuenow',p.percent);meter.removeAttribute('aria-valuetext');}
      else{meter.removeAttribute('aria-valuenow');meter.setAttribute('aria-valuetext',labels[state]);}
      card.querySelector('[data-fluid-updated]').textContent=fresh?'Updated '+new Date(p.updated_at*1000).toLocaleTimeString()+'. Refreshes automatically.':'No fresh reading. Check the exhibit connection or sensor.';
    }
    async function refresh(){
      if(busy||document.hidden)return;busy=true;
      const abort=new AbortController();const timer=setTimeout(()=>abort.abort(),4000);
      try{
        const url=new URL('/fluid-status.php',location.origin);url.searchParams.set('component',card.dataset.fluidComponent);
        if(token)url.searchParams.set('token',token);
        const r=await fetch(url,{credentials:'same-origin',cache:'no-store',signal:abort.signal,headers:{Accept:'application/json'}});
        if(!r.ok)throw new Error();display(await r.json());
      }catch{display(null);}finally{clearTimeout(timer);busy=false;}
    }
    refresh();setInterval(refresh,10000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  }
})();
