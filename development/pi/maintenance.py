"""Local, allowlisted bench maintenance; only the game process owns serial."""
import json
from pathlib import Path
import re
import time
import uuid
from dataclasses import asdict
from operator_settings import validate_settings,validate_thresholds,DEFAULT_SETTINGS
from receiver_calibrate import propose,summarize
from game_audio import MEDIA
from game_reporting import atomic_json

ID = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\Z')
COLORS = ('RED','GREEN','BLUE','YELLOW','PURPLE','OFF')
ACTIONS = ('enter_maintenance','leave_maintenance','stop_game','snapshot','audio_play','stop_audio','audio_mute','rgb_test','display_test','restart_game','rfid_start','rfid_end','rfid_reset','keypad_start','keypad_end','beams_check','receiver_auto','receiver_capture','receiver_apply','receiver_thresholds','module_test','laser_align','game_settings','start_lock','audio_volume','audio_output_test','service_start','service_stop','reboot_pi','software_reinstall')


def validate(command, identity, wall):
    if not isinstance(command,dict) or set(command) != {'id','device_id','action','params','expires_at'}: raise ValueError('invalid_command')
    if not isinstance(command['id'],str) or not ID.fullmatch(command['id']): raise ValueError('invalid_command')
    if command['device_id'] != identity: raise ValueError('wrong_component')
    if command['action'] not in ACTIONS: raise ValueError('unsupported_action')
    if type(command['expires_at']) is not int or command['expires_at'] <= wall: raise ValueError('expired')
    if command['expires_at'] > wall+120: raise ValueError('invalid_expiry')
    p=command['params'];action=command['action']
    if not isinstance(p,dict): raise ValueError('invalid_parameters')
    if action=='audio_play':
        if set(p)!= {'clip'} or p['clip'] not in MEDIA: raise ValueError('invalid_clip')
    elif action=='audio_mute':
        if set(p)!= {'muted'} or type(p['muted']) is not bool: raise ValueError('invalid_parameters')
    elif action=='rgb_test':
        if set(p)!= {'color'} or p['color'] not in COLORS: raise ValueError('invalid_color')
    elif action=='receiver_capture':
        if set(p)!={'phase'} or p['phase'] not in ('blocked','clear','blocked_check'):raise ValueError('invalid_capture_phase')
    elif action=='receiver_apply':
        if set(p)!={'candidate_id'} or not isinstance(p['candidate_id'],str) or not ID.fullmatch(p['candidate_id']):raise ValueError('invalid_calibration_candidate')
    elif action=='receiver_thresholds':validate_thresholds(p)
    elif action=='game_settings':validate_settings(p)
    elif action=='start_lock':
        if set(p)!={'locked'} or type(p['locked']) is not bool:raise ValueError('invalid_start_lock')
    elif action=='audio_volume':
        if set(p)!={'percent'} or type(p['percent']) is not int or not 0<=p['percent']<=100:raise ValueError('invalid_volume')
    elif p: raise ValueError('invalid_parameters')
    return action,p


class Maintenance:
    def __init__(self, folder, identity, audio, effects, wall=time.time):
        self.folder=Path(folder);self.identity=identity;self.audio=audio;self.effects=effects;self.wall=wall
        for name in ('inbox','results','outbox'):(self.folder/name).mkdir(parents=True,exist_ok=True,mode=0o700)
        self.enabled=False;self.local_until=0;self.pending=None;self.test=None;self.next_scan=0
        self.send=None;self.raw=None;self.raw_at=-100;self.last_key='none';self.last_key_at=0;self.connected=False
        self.thresholds=dict(break_below=20,clear_above=41);self.capture_values={};self.candidate=None;self.next_live=0
        self.beam_check=None;self.keypad_session=None;self.rfid_session=None
        self.volume=100;self.play_locked=False;self.saved_settings=None
        receiver_file=self.folder/'receiver-settings.json'
        if receiver_file.exists():self.thresholds=validate_thresholds(json.loads(receiver_file.read_text())['thresholds'])
        settings_file=self.folder/'game-settings.json'
        if settings_file.exists():self.saved_settings=validate_settings(json.loads(settings_file.read_text()))

        try:
            saved=json.loads((self.folder/'state.json').read_text())
            self.enabled=saved.get('enabled') is True
            self.local_until=float(saved.get('local_until',0))
            self.audio.muted=self.effects.muted=saved.get('muted') is True
            self.play_locked=saved.get('play_locked') is True
            volume=saved.get('volume',100)
            self.volume=volume if type(volume) is int and 0<=volume<=100 else 100
            self.audio.volume=self.effects.volume=self.volume/100
        except (OSError,ValueError,TypeError):pass

    def save(self):
        self.next_live=0
        atomic_json(self.folder/'state.json',dict(enabled=self.enabled,local_until=self.local_until,muted=self.audio.muted,volume=self.volume,play_locked=self.play_locked))

    def local_enabled(self):return self.enabled and self.wall()<self.local_until

    def metrics(self):
        return dict(maintenance_protocol=2,maintenance_enabled=self.enabled,
            maintenance_local_enabled=self.local_enabled(),maintenance_pending=self.pending is not None,
            maintenance_test_active=self.test is not None or self.keypad_active() or self.rfid_active())

    def configure_controls(self,controls):
        controls.play_locked=self.play_locked
        if self.saved_settings:controls.configure(self.saved_settings)

    def receive_light(self,value,now):
        self.raw=value;self.raw_at=now
        if self.test and self.test['kind'] in ('capture','auto','beams') and self.test.get('sample_after') is not None and now>=self.test['sample_after'] and len(self.test['values'])<100:self.test['values'].append(value)

    def live(self,controls,now):
        settings=asdict(controls.settings);settings.pop('beam_count',None)
        settings['enabled_beams']=list(controls.settings.enabled_beams or (True,True));settings['available_modes']=list(controls.allowed_modes)
        return dict(device_id=self.identity,sampled_at=int(self.wall()),protocol=2,connected=self.connected,
            **self.metrics(),local_until=int(self.local_until),play_locked=self.play_locked,
            receiver=dict(pin='A0',raw=self.raw if now-self.raw_at<1 else None,blocked=controls.levels[0],thresholds=self.thresholds,
                captures={key:summarize(v) for key,v in self.capture_values.items()},candidate=self.candidate),
            rfid=dict(diagnostics=controls.reader_diagnostics,ready=controls.reader_ready,scans_this_run=controls.scan_count,seconds_since_scan=round(now-controls.last_scan_at,1) if controls.last_scan_at is not None else None,entry=controls.entry.status(now)),
            settings=settings,inputs=list(controls.levels),last_key=self.last_key,last_key_at=int(self.last_key_at),
            audio=dict(volume=self.volume,muted=self.audio.muted,backend=str(self.audio.backend or 'unavailable'),output_device=self.audio.environment.get('ZOCO_AUDIO_TARGET','configured default') if hasattr(self.audio,'environment') else 'configured default'),
            capabilities=dict(module_count=1,module_pixels=16,status_pixels=42,status_rows=14,ring_customization=False,laser_switching=True,powered_calibration=True,automatic_calibration=True,all_beams_check=True,keypad_layout='storm_12',staff_key_controls=True,usb_objective=True,isolated_keypad_test=True,rfid_test=True,rfid_reinitialize=True,rfid=True,hazer=False,door=False),
            firmware_version=getattr(self,'version','unconfirmed'),python_version=getattr(self,'version','unconfirmed'),serial_port=getattr(self,'serial_port','unconfirmed'),
            usb_input=getattr(self,'usb_input',None),rfid_test=self.rfid_snapshot(controls),keypad_test=self.keypad_session,staff_hold_seconds=getattr(self,'staff_hold_seconds',0),laser_command_on=self.display()[0],laser_seconds_remaining=max(0,int(self.test['until']-now)) if self.test and self.test['kind'] in ('alignment','module','capture','auto','beams') else 0,
            test=self.test['kind'] if self.test else ('keypad' if self.keypad_active() else 'rfid' if self.rfid_active() else 'none'),capture_samples=len(self.test['values']) if self.test and self.test['kind'] in ('capture','auto','beams') else 0,
            beam_check=self.beam_check,beam_check_step=self.test['phase'] if self.test and self.test['kind']=='beams' else 'none',
            calibration_step=self.test['phase'] if self.test and self.test['kind']=='auto' else ('saving' if self.test and self.test['kind']=='apply' else 'none'))

    def publish(self,controls,now):
        if now>=self.next_live:
            self.next_live=now+(1 if self.enabled or self.pending else 5)
            atomic_json(self.folder/'live.json',self.live(controls,now))

    def apply_thresholds(self,command,thresholds,controls,now):
        if not self.send:self.complete(command,'failed','serial_not_ready',controls);return
        previous=dict(self.thresholds)
        self.test=dict(kind='apply',command=command,until=now+2)
        def acknowledged():
            if not self.test or self.test['command']['id']!=command['id']:
                self.send('CAL {break_below} {clear_above}'.format(**previous),'OK CAL {break_below} {clear_above}'.format(**previous));return
            record=dict(thresholds=thresholds,applied_at=int(self.wall()),command_id=command['id'],candidate=self.candidate)
            atomic_json(self.folder/'receiver-settings.json',record)
            self.thresholds=dict(thresholds);self.test=None
            if command['action']=='receiver_auto' and self.candidate:self.candidate['applied']=True
            self.complete(command,'completed','receiver_thresholds_applied',controls)
        text='CAL {break_below} {clear_above}'.format(**thresholds)
        self.send(text,'OK '+text,acknowledged)

    def automatic_tick(self,controls,now,serial_idle,previous):
        test=self.test
        if now>test['until']:
            self.cancel_test(controls,'automatic_calibration_timed_out_check_connection');return
        if test.get('sample_after') is None and serial_idle and previous==self.display():
            # Allow both Nano ring bounces to finish before background/beam measurements.
            test['sample_after']=now+(3.0 if test['phase']=='clear' else 2.5)
        if len(test['values'])<100:return
        phase=test['phase'];self.capture_values[phase]=list(test['values'])
        phases=('blocked','clear','blocked_check');index=phases.index(phase)
        if index<2:
            test.update(phase=phases[index+1],values=[],sample_after=None);self.next_live=0;return
        proposal=propose(self.capture_values['blocked'],self.capture_values['clear'],self.capture_values['blocked_check'])
        if proposal['usable']:
            off,on,again=(proposal[k] for k in phases)
            gap=on['p05']-max(off['p95'],again['p95'])
            if abs(off['median']-again['median'])>max(5,gap*.15):
                proposal.update(usable=False,reason='Background light changed during calibration; keep the beam path clear and retry.')
            elif any(v['p95']-v['p05']>max(10,gap*.30) for v in (off,on,again)):
                proposal.update(usable=False,reason='Light readings were unstable; check aim, wiring and ambient light, then retry.')
        self.candidate=dict(id=str(uuid.uuid4()),created_at=int(self.wall()),mode='automatic_off_on_off',proposal=proposal)
        atomic_json(self.folder.parent/'calibration'/('auto-'+test['command']['id']+'.json'),
                    dict(mode='automatic_off_on_off',module=1,pin='A0',readings=self.capture_values,candidate=self.candidate,applied_to_game=False))
        if not proposal['usable']:
            reason='automatic_calibration_failed_keep_path_clear_check_aim_and_wiring'
            self.test=None;self.complete(test['command'],'failed',reason,controls);return
        command=test['command'];self.test=None
        self.apply_thresholds(command,dict(break_below=proposal['proposed_break_threshold'],clear_above=proposal['proposed_clear_threshold']),controls,now)

    def beams_tick(self,controls,now,serial_idle,previous):
        test=self.test
        if now>test['until']:
            self.cancel_test(controls,'beam_test_timed_out_check_connection');return
        if test['phase']=='off':
            # Report completion only after the module LOW command is acknowledged.
            if serial_idle and previous==self.display():
                self.beam_check.update(status='completed',finished_at=int(self.wall()),outputs_off_confirmed=True)
                atomic_json(self.folder/'beam-check.json',self.beam_check)
                command=test['command'];self.test=None
                self.complete(command,'completed','all_beams_clear' if self.beam_check['all_clear'] else 'beam_test_attention_required',controls)
            return
        if test.get('sample_after') is None and serial_idle and previous==self.display():
            test['sample_after']=now+3.0
        if len(test['values'])<100:return
        sample=summarize(test['values']);clear=self.thresholds['clear_above']
        state='clear' if sample['minimum']>=clear else ('not_detected' if sample['maximum']<clear else 'unstable')
        self.beam_check.update(all_clear=state=='clear',modules=[dict(module=1,pin='A0',state=state,clear_above=clear,**sample)])
        test['phase']='off';self.next_live=0

    def complete(self,command,status,reason,controls):
        self.next_live=0
        path=self.folder/'results'/(command['id']+'.json')
        if not path.exists():atomic_json(path,dict(id=command['id'],device_id=self.identity,status=status,reason=reason,
            executed_at=int(self.wall()),snapshot=dict(self.metrics(),inputs=list(controls.levels),game_running=controls.game is not None,rfid=dict(diagnostics=controls.reader_diagnostics,ready=controls.reader_ready,scans_this_run=controls.scan_count,entry_state=controls.entry.reason),receiver=dict(raw=self.raw,thresholds=self.thresholds,captures={k:summarize(v) for k,v in self.capture_values.items()},candidate=self.candidate),play_locked=self.play_locked,volume=self.volume,beam_check=self.beam_check,keypad_test=self.keypad_session if command.get('action') in ('keypad_start','keypad_end') else None,rfid_test=self.rfid_snapshot(controls) if command.get('action') in ('rfid_start','rfid_end','rfid_reset') else None)))
        atomic_json(self.folder/'outbox'/path.name,json.loads(path.read_text()))
        (self.folder/'inbox'/(command['id']+'.json')).unlink(missing_ok=True)

    def rfid_active(self):return self.rfid_session is not None and self.rfid_session['status']=='running'

    def rfid_snapshot(self,controls):
        if self.rfid_session is None:return None
        result=dict(self.rfid_session)
        for key,base in (('tag_responses','responses_at_start'),('selection_failures','failures_at_start')):
            delta=max(0,controls.reader_diagnostics.get(key,0)-result.pop(base));result[key]=result.get(key,delta)
        return result

    def rfid_scan(self):
        if self.rfid_active():
            self.rfid_session['scans']+=1;self.rfid_session['last_scan_at']=int(self.wall());self.next_live=0

    def end_rfid(self,reason,controls):
        if self.rfid_active():
            stats=self.rfid_snapshot(controls)
            self.rfid_session.update(tag_responses=stats['tag_responses'],selection_failures=stats['selection_failures'])
            self.rfid_session.update(status='ended',reason=reason,ended_at=int(self.wall()));self.next_live=0

    def reset_rfid(self,command,controls,now):
        if self.test or not self.send:self.complete(command,'failed','serial_not_ready_or_test_busy',controls);return
        self.test=dict(kind='rfid_reset',command=command,until=now+3)
        def acknowledged():
            if not self.test or self.test['command']['id']!=command['id']:return
            self.test=None
            self.complete(command,'completed' if controls.reader_ready else 'failed','rfid_reader_reinitialized' if controls.reader_ready else 'rfid_reader_still_missing_check_power_and_wiring',controls)
        self.send('RFID RESET','RFID STATUS',acknowledged)

    def keypad_active(self):return self.keypad_session is not None and self.keypad_session['status']=='running'

    def keypad_key(self,key):
        if not self.keypad_active():return
        session=self.keypad_session
        session.update(last_key=key,last_key_at=int(self.wall()),press_count=session['press_count']+1)
        if key not in session['seen']:session['seen'].append(key)
        self.next_live=0

    def end_keypad(self,reason):
        if self.keypad_active():
            self.keypad_session.update(status='ended',reason=reason,ended_at=int(self.wall()))
            self.staff_hold_seconds=0;self.next_live=0

    def stop_audio(self):self.audio.cancel();self.effects.cancel()

    def cancel_test(self,controls,reason='cancelled'):
        self.end_keypad(reason);self.end_rfid(reason,controls)
        if self.test:
            if self.test['kind']=='beams':
                self.beam_check.update(status='cancelled' if reason=='cancelled' else 'unconfirmed',reason=reason,all_clear=False,finished_at=int(self.wall()),outputs_off_confirmed=False)
                atomic_json(self.folder/'beam-check.json',self.beam_check)
            self.complete(self.test['command'],'failed',reason,controls);self.test=None
        self.stop_audio()

    def local_key(self,key,controls):
        if self.keypad_active():return True
        if self.pending and self.pending['expires_at']<=self.wall():
            pending=self.pending;self.pending=None
            self.complete(pending,'expired','local_confirmation_expired',controls)
        if key in ('C','5') and (self.pending or self.enabled):
            self.enabled=True;self.local_until=self.wall()+300;self.save()
            if self.pending:
                pending=self.pending;self.pending=None;self.complete(pending,'completed','maintenance_enabled',controls)
            return True
        if key=='B' and (self.pending or self.enabled):
            self.cancel_test(controls)
            if self.pending:
                pending=self.pending;self.pending=None;self.complete(pending,'failed','local_cancelled',controls)
            self.enabled=False;self.local_until=0;controls.result=None;self.save()
            return True
        if key=='D' or (key=='*' and (self.pending or self.enabled)):
            self.cancel_test(controls)
            if self.pending:
                pending=self.pending;self.pending=None;self.complete(pending,'failed','local_cancelled',controls)
            return self.enabled
        return self.enabled or self.pending is not None

    def display(self):
        if self.test and self.test['kind']=='beams':return self.test['phase']=='on',False,0,'YELLOW'
        if self.test and self.test['kind']=='auto':return self.test['phase']=='clear',False,0,'YELLOW'
        if self.test and self.test['kind']=='rgb':return False,False,0,self.test['color']
        if self.test and self.test['kind'] in ('module','alignment','capture'):return True,False,0,'YELLOW'
        if self.test and self.test['kind']=='display':return False,False,5999,'BLUE'
        return False,False,0,'BLUE' if self.enabled else 'YELLOW'

    def tick(self,controls,now,serial_idle=False,previous=None):
        wall=self.wall()
        if self.rfid_active():
            if not self.local_enabled():self.end_rfid('local_enable_expired',controls)
            elif wall>=self.rfid_session['ends_at']:self.end_rfid('time_limit_reached',controls)
        if self.keypad_active():
            if not self.local_enabled():self.end_keypad('local_enable_expired')
            elif wall>=self.keypad_session['ends_at']:self.end_keypad('time_limit_reached')
        if self.pending and self.pending['expires_at']<=wall:
            pending=self.pending;self.pending=None;self.complete(pending,'expired','local_confirmation_expired',controls)
        if self.test:
            test=self.test
            if test['command']['expires_at']<=wall or not self.local_enabled():self.cancel_test(controls,'local_enable_expired')
            elif test['kind']=='beams':self.beams_tick(controls,now,serial_idle,previous)
            elif test['kind']=='auto':self.automatic_tick(controls,now,serial_idle,previous)
            elif test['kind']=='capture':
                # Begin settling only after the output command has been acknowledged.
                if test.get('sample_after') is None and serial_idle and previous and previous[0]:test['sample_after']=now+.5
                if len(test['values'])>=100:
                    phase=test['phase'];self.capture_values[phase]=list(test['values'])
                    if set(self.capture_values)=={'blocked','clear','blocked_check'}:
                        result=propose(self.capture_values['blocked'],self.capture_values['clear'],self.capture_values['blocked_check'])
                        self.candidate=dict(id=str(uuid.uuid4()),created_at=int(wall),proposal=result)
                    atomic_json(self.folder.parent/'calibration'/('portal-'+test['command']['id']+'.json'),dict(phase=phase,readings=test['values'],captured_at=int(wall),candidate=self.candidate,applied_to_game=False))
                    self.test=None;self.complete(test['command'],'completed','receiver_sample_captured',controls)
                elif now>test['until']:self.cancel_test(controls,'receiver_sample_timeout')
            elif test['kind']=='rfid_reset':
                if now>test['until']:self.cancel_test(controls,'rfid_reinitialize_unconfirmed')
            elif test['kind']=='apply':
                if now>test['until']:self.cancel_test(controls,'receiver_apply_unconfirmed')
            elif test['kind']=='audio':
                if self.audio.error:
                    self.stop_audio();self.complete(test['command'],'failed',self.audio.error,controls);self.test=None
                elif getattr(self.audio,'process',None) is None and not getattr(self.audio,'pending',[]) and getattr(self.audio,'last_cue',None)==test.get('clip',test['command']['params'].get('clip','entrance')):
                    self.complete(test['command'],'completed','playback_finished_speaker_unconfirmed',controls);self.test=None
                elif now>test['until']:
                    self.stop_audio();self.complete(test['command'],'failed','audio_test_timeout',controls);self.test=None
            elif now>=test['until']:
                test['color']='BLUE';test['kind']='reset'
                if serial_idle and previous==self.display():self.complete(test['command'],'completed','test_finished_physical_output_unconfirmed',controls);self.test=None
        if now<self.next_scan:return
        self.next_scan=now+.15
        commands=[]
        for path in list((self.folder/'inbox').glob('*.json'))[:20]:
            if not ID.fullmatch(path.stem):continue
            try:
                if path.stat().st_size>4096:raise ValueError('invalid_command')
                command=json.loads(path.read_text());action,params=validate(command,self.identity,wall)
                if command['id']!=path.stem:raise ValueError('invalid_command')
            except (OSError,ValueError,TypeError,KeyError):
                self.complete(dict(id=path.stem),'failed','invalid_or_expired_command',controls);continue
            if (self.folder/'results'/(path.stem+'.json')).exists():path.unlink(missing_ok=True);continue
            commands.append(command)
        commands.sort(key=lambda c:0 if c['action'] in ('stop_game','stop_audio') else 1)
        for command in commands:
            if (self.folder/'results'/(command['id']+'.json')).exists():continue
            action,params=validate(command,self.identity,wall)
            if self.pending and command['id']==self.pending['id']:continue
            if self.test and command['id']==self.test['command']['id']:continue
            if action=='stop_game':
                if controls.game:controls.game.finish('stopped');controls.tick(now)
                self.cancel_test(controls)
                if self.pending:self.complete(self.pending,'failed','cancelled',controls);self.pending=None
                self.complete(command,'completed','game_stopped',controls)
                for other in commands:
                    if other['action'] not in ('stop_game','stop_audio','snapshot','leave_maintenance') and not (self.folder/'results'/(other['id']+'.json')).exists():self.complete(other,'failed','cancelled_by_stop',controls)
            elif action=='stop_audio':
                self.cancel_test(controls);self.complete(command,'completed','sound_stopped',controls)
                for other in commands:
                    if other['action']=='audio_play' and not (self.folder/'results'/(other['id']+'.json')).exists():self.complete(other,'failed','cancelled_by_stop',controls)
            elif action=='rfid_end':
                self.end_rfid('ended_from_portal',controls);self.complete(command,'completed','rfid_test_ended',controls)
            elif action=='keypad_end':
                self.end_keypad('ended_from_portal');self.complete(command,'completed','keypad_test_ended',controls)
            elif action=='snapshot':self.complete(command,'completed','observed_inputs_captured',controls)
            elif action=='enter_maintenance':
                if controls.game:controls.game.finish('stopped');controls.tick(now)
                controls.result=None;self.cancel_test(controls)
                if self.enabled and self.local_enabled():self.complete(command,'completed','maintenance_already_enabled',controls)
                elif self.pending:self.complete(command,'failed','another_request_pending',controls)
                else:self.pending=command
            elif action=='leave_maintenance':
                self.cancel_test(controls)
                if self.pending:self.complete(self.pending,'failed','cancelled',controls);self.pending=None
                self.enabled=False;self.local_until=0;controls.result=None;self.save()
                self.complete(command,'completed','returned_to_idle',controls)
            elif action=='start_lock':
                self.play_locked=params['locked'];controls.play_locked=self.play_locked;self.save()
                self.complete(command,'completed','new_games_disabled' if self.play_locked else 'new_games_enabled',controls)
            elif not self.local_enabled():self.complete(command,'failed','press_5_in_maintenance_first',controls)
            elif action=='rfid_reset' and not self.keypad_active():self.reset_rfid(command,controls,now)
            elif self.test or self.keypad_active() or self.rfid_active():self.complete(command,'failed','test_busy',controls)
            elif action=='rfid_start':
                self.stop_audio();controls.entry.reset('maintenance')
                self.rfid_session=dict(id=command['id'],status='running',started_at=int(wall),ends_at=int(wall)+120,scans=0,last_scan_at=None,responses_at_start=controls.reader_diagnostics.get('tag_responses',0),failures_at_start=controls.reader_diagnostics.get('selection_failures',0))
                self.next_live=0;self.complete(command,'completed','rfid_test_started_two_minutes',controls)
            elif action=='keypad_start':
                self.stop_audio()
                self.keypad_session=dict(id=command['id'],status='running',started_at=int(wall),ends_at=int(wall)+120,last_key=None,last_key_at=None,press_count=0,seen=[])
                self.next_live=0;self.complete(command,'completed','keypad_test_started_two_minutes',controls)
            elif action=='beams_check':
                enabled=list(controls.settings.enabled_beams or (True,True))[0]
                self.beam_check=dict(command_id=command['id'],started_at=int(wall),status='running',all_clear=False,configured_count=1,tested_count=1 if enabled else 0,outputs_off_confirmed=False,modules=[])
                atomic_json(self.folder/'beam-check.json',self.beam_check)
                if not enabled:
                    self.beam_check.update(status='completed',reason='no_enabled_laser_receivers',modules=[dict(module=1,pin='A0',state='disabled')])
                    atomic_json(self.folder/'beam-check.json',self.beam_check)
                    self.complete(command,'completed','no_enabled_laser_receivers',controls)
                else:self.test=dict(kind='beams',command=command,phase='on',values=[],sample_after=None,until=now+20)
                self.next_live=0
            elif action=='receiver_auto':
                self.capture_values={};self.candidate=None
                self.test=dict(kind='auto',command=command,phase='blocked',values=[],sample_after=None,until=now+40)
                self.next_live=0
            elif action=='receiver_capture':
                phase=params['phase']
                if phase=='blocked':self.capture_values={};self.candidate=None
                if (phase=='clear' and 'blocked' not in self.capture_values) or (phase=='blocked_check' and not {'blocked','clear'}.issubset(self.capture_values)):
                    self.complete(command,'failed','capture_blocked_then_clear_then_blocked_check',controls)
                elif now-self.raw_at>1:self.complete(command,'failed','receiver_data_not_ready',controls)
                else:self.test=dict(kind='capture',command=command,phase=phase,values=[],sample_after=None,until=now+15)
            elif action=='receiver_apply':
                candidate=self.candidate
                if not candidate or candidate['id']!=params['candidate_id'] or wall-candidate['created_at']>1800 or not candidate['proposal']['usable']:
                    self.complete(command,'failed','calibration_candidate_invalid_or_stale',controls)
                else:self.apply_thresholds(command,dict(break_below=candidate['proposal']['proposed_break_threshold'],clear_above=candidate['proposal']['proposed_clear_threshold']),controls,now)
            elif action=='receiver_thresholds':self.apply_thresholds(command,params,controls,now)
            elif action=='game_settings':
                value=validate_settings(params);atomic_json(self.folder/'game-settings.json',value)
                controls.configure(value);self.saved_settings=value
                self.complete(command,'completed','game_settings_saved',controls)
            elif action=='audio_volume':
                if not self.audio.backend or not str(self.audio.backend).endswith('pw-play'):
                    self.complete(command,'failed','volume_requires_pipewire_player',controls)
                else:
                    self.volume=params['percent'];self.audio.volume=self.effects.volume=self.volume/100;self.stop_audio();self.save()
                    self.complete(command,'completed','audio_playback_level_saved',controls)
            elif action=='module_test':self.test=dict(kind='module',command=command,until=now+5)
            elif action=='laser_align':self.test=dict(kind='alignment',command=command,until=now+30)
            elif action=='audio_mute':
                self.audio.muted=self.effects.muted=params['muted'];self.stop_audio();self.save()
                self.complete(command,'completed','audio_muted' if params['muted'] else 'audio_unmuted',controls)
            elif action in ('audio_play','audio_output_test'):
                if action=='audio_output_test':params={'clip':'entrance'}
                if not self.audio.enabled or self.audio.muted or not self.audio.assets_ready or not self.audio.backend:
                    self.complete(command,'failed','audio_not_ready_or_muted',controls)
                else:
                    self.effects.cancel();self.audio.error='';self.audio.queue(params['clip'],priority=True)
                    self.test=dict(command=command,kind='audio',clip=params['clip'],until=now+self.audio.durations[params['clip']]+3)
            elif action in ('rgb_test','display_test'):
                self.test=dict(command=command,kind='rgb' if action=='rgb_test' else 'display',color=params.get('color','BLUE'),until=now+5)
            else:self.complete(command,'failed','restart_is_bridge_action',controls)
