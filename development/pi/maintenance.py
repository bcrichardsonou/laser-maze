"""Local, allowlisted bench maintenance; only the game process owns serial."""
import json
from pathlib import Path
import re
import time
from game_audio import MEDIA
from game_reporting import atomic_json

ID = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\Z')
COLORS = ('RED','GREEN','BLUE','YELLOW','PURPLE','OFF')
ACTIONS = ('enter_maintenance','leave_maintenance','stop_game','snapshot','audio_play','stop_audio','audio_mute','rgb_test','display_test','restart_game')


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
    elif p: raise ValueError('invalid_parameters')
    return action,p


class Maintenance:
    def __init__(self, folder, identity, audio, effects, wall=time.time):
        self.folder=Path(folder);self.identity=identity;self.audio=audio;self.effects=effects;self.wall=wall
        for name in ('inbox','results','outbox'):(self.folder/name).mkdir(parents=True,exist_ok=True,mode=0o700)
        self.enabled=False;self.local_until=0;self.pending=None;self.test=None;self.next_scan=0
        try:
            saved=json.loads((self.folder/'state.json').read_text())
            self.enabled=saved.get('enabled') is True
            self.local_until=float(saved.get('local_until',0))
            self.audio.muted=self.effects.muted=saved.get('muted') is True
        except (OSError,ValueError,TypeError):pass

    def save(self):
        atomic_json(self.folder/'state.json',dict(enabled=self.enabled,local_until=self.local_until,muted=self.audio.muted))

    def local_enabled(self):return self.enabled and self.wall()<self.local_until

    def metrics(self):
        return dict(maintenance_protocol=1,maintenance_enabled=self.enabled,
            maintenance_local_enabled=self.local_enabled(),maintenance_pending=self.pending is not None,
            maintenance_test_active=self.test is not None)

    def complete(self,command,status,reason,controls):
        path=self.folder/'results'/(command['id']+'.json')
        if not path.exists():atomic_json(path,dict(id=command['id'],device_id=self.identity,status=status,reason=reason,
            executed_at=int(self.wall()),snapshot=dict(self.metrics(),inputs=list(controls.levels),game_running=controls.game is not None)))
        atomic_json(self.folder/'outbox'/path.name,json.loads(path.read_text()))
        (self.folder/'inbox'/(command['id']+'.json')).unlink(missing_ok=True)

    def stop_audio(self):self.audio.cancel();self.effects.cancel()

    def cancel_test(self,controls,reason='cancelled'):
        if self.test:self.complete(self.test['command'],'failed',reason,controls);self.test=None
        self.stop_audio()

    def local_key(self,key,controls):
        if self.pending and self.pending['expires_at']<=self.wall():
            pending=self.pending;self.pending=None
            self.complete(pending,'expired','local_confirmation_expired',controls)
        if key=='C' and (self.pending or self.enabled):
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
        if key=='D':
            self.cancel_test(controls)
            if self.pending:
                pending=self.pending;self.pending=None;self.complete(pending,'failed','local_cancelled',controls)
            return self.enabled
        return self.enabled or self.pending is not None

    def display(self):
        if self.test and self.test['kind']=='rgb':return False,False,0,self.test['color']
        if self.test and self.test['kind']=='display':return False,False,5999,'BLUE'
        return False,False,0,'BLUE' if self.enabled else 'YELLOW'

    def tick(self,controls,now,serial_idle=False,previous=None):
        wall=self.wall()
        if self.pending and self.pending['expires_at']<=wall:
            pending=self.pending;self.pending=None;self.complete(pending,'expired','local_confirmation_expired',controls)
        if self.test:
            test=self.test
            if test['command']['expires_at']<=wall or not self.local_enabled():self.cancel_test(controls,'local_enable_expired')
            elif test['kind']=='audio':
                if self.audio.error:
                    self.stop_audio();self.complete(test['command'],'failed',self.audio.error,controls);self.test=None
                elif getattr(self.audio,'process',None) is None and not getattr(self.audio,'pending',[]) and getattr(self.audio,'last_cue',None)==test['command']['params']['clip']:
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
                    if other['action'] in ('enter_maintenance','audio_play','rgb_test','display_test','restart_game') and not (self.folder/'results'/(other['id']+'.json')).exists():self.complete(other,'failed','cancelled_by_stop',controls)
            elif action=='stop_audio':
                self.cancel_test(controls);self.complete(command,'completed','sound_stopped',controls)
                for other in commands:
                    if other['action']=='audio_play' and not (self.folder/'results'/(other['id']+'.json')).exists():self.complete(other,'failed','cancelled_by_stop',controls)
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
            elif not self.local_enabled():self.complete(command,'failed','press_C_in_maintenance_first',controls)
            elif self.test:self.complete(command,'failed','test_busy',controls)
            elif action=='audio_mute':
                self.audio.muted=self.effects.muted=params['muted'];self.stop_audio();self.save()
                self.complete(command,'completed','audio_muted' if params['muted'] else 'audio_unmuted',controls)
            elif action=='audio_play':
                if not self.audio.enabled or self.audio.muted or not self.audio.assets_ready or not self.audio.backend:
                    self.complete(command,'failed','audio_not_ready_or_muted',controls)
                else:
                    self.effects.cancel();self.audio.error='';self.audio.queue(params['clip'],priority=True)
                    self.test=dict(command=command,kind='audio',until=now+self.audio.durations[params['clip']]+3)
            elif action in ('rgb_test','display_test'):
                self.test=dict(command=command,kind='rgb' if action=='rgb_test' else 'display',color=params.get('color','BLUE'),until=now+5)
            else:self.complete(command,'failed','restart_is_bridge_action',controls)
