import { App } from '@capacitor/app';
import { Capacitor, registerPlugin } from '@capacitor/core';
import { Preferences } from '@capacitor/preferences';
import { KeepAwake } from '@capacitor-community/keep-awake';
import { ScreenOrientation } from '@capacitor/screen-orientation';
import { BarcodeScanner, BarcodeFormat, GoogleBarcodeScannerModuleInstallState } from '@capacitor-mlkit/barcode-scanning';
import { SecureStorage } from '@aparajita/capacitor-secure-storage';

const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const Immersive=registerPlugin('Immersive');
let ws;
const carry={x:0,y:0};
const onlineIds=new Set();
let laptops=[];
let activeLaptop=null;
let hideTimer;
const RETRY_DELAYS=[1000,2000,4000,8000,10000];

function setHomeStatus(message){$('#home-status').textContent=message}
function setScannerProgress(message){
  const status=$('#scanner-progress');
  status.textContent=message;
  status.hidden=!message;
}
function showPairFallback(message=''){
  $('#pair-error').textContent=message;
  $('#pair-fallback').hidden=false;
}
function setConnectionStatus(connected,message){
  $('#dot').classList.toggle('on',connected);
  $('#status').textContent=message;
}
function showControls(laptop){
  activeLaptop=laptop;
  $('#home-screen').hidden=true;
  $('#control-screen').hidden=false;
  $('#barName').textContent=laptop.name;
  $('#expiry-banner').hidden=true;
  $('#reconnect-overlay').hidden=true;
  if(Capacitor.isNativePlatform())Immersive.setEnabled({enabled:true}).catch(error=>console.error('Could not enter immersive mode:',error));
}
async function showHome(){
  $('#control-screen').hidden=true;
  $('#home-screen').hidden=false;
  $('#expiry-banner').hidden=true;
  $('#reconnect-overlay').hidden=true;
  if(Capacitor.isNativePlatform())try{await Immersive.setEnabled({enabled:false})}catch(error){console.error('Could not leave immersive mode:',error)}
  try{await KeepAwake.allowSleep()}catch(error){console.error('Could not allow screen sleep:',error)}
  try{await ScreenOrientation.unlock()}catch(error){console.error('Could not unlock screen orientation:',error)}
  activeLaptop=null;
  await renderLaptops();
}
function send(o){if(ws&&ws.readyState===WebSocket.OPEN){ws.send(JSON.stringify(o));return true}return false}
const buzz=()=>navigator.vibrate&&navigator.vibrate(8);

async function preference(key, fallback=null){
  const {value}=await Preferences.get({key});
  return value===null?fallback:value;
}
async function saveLaptops(){
  await Preferences.set({key:'laptops',value:JSON.stringify(laptops)});
}
async function loadLaptops(){
  const value=await preference('laptops','[]');
  const saved=JSON.parse(value);
  if(!Array.isArray(saved))throw new Error('Saved laptop list is invalid.');
  laptops=saved;
  $('#auto-connect-toggle').checked=(await preference('autoConnect','false'))==='true';
}
function formatLastUsed(timestamp){
  if(!timestamp)return 'Not connected yet';
  return `Last used ${new Date(timestamp).toLocaleString()}`;
}
async function renderLaptops(){
  const list=$('#laptop-list');
  list.replaceChildren();
  if(!laptops.length){
    const empty=document.createElement('p');
    empty.textContent='No saved laptops yet.';
    list.appendChild(empty);
    return;
  }
  for(const laptop of laptops){
    const button=document.createElement('button');
    button.className='laptop';
    button.type='button';
    const dot=document.createElement('span');
    dot.className=`online-dot${onlineIds.has(laptop.id)?' on':''}`;
    const info=document.createElement('span');
    info.className='laptop-info';
    const name=document.createElement('span');
    name.className='laptop-name';
    name.textContent=laptop.name;
    const last=document.createElement('span');
    last.className='laptop-last';
    last.textContent=formatLastUsed(laptop.lastUsed);
    info.append(name,last);
    button.append(dot,info);
    let holdTimer=null,longPressed=false;
    button.addEventListener('pointerdown',()=>{
      longPressed=false;
      holdTimer=setTimeout(()=>{longPressed=true;manageLaptop(laptop).catch(error=>setHomeStatus(error.message))},650);
    });
    ['pointerup','pointercancel','pointerleave'].forEach(event=>button.addEventListener(event,()=>clearTimeout(holdTimer)));
    button.addEventListener('contextmenu',event=>{
      event.preventDefault();
      clearTimeout(holdTimer);
      if(!longPressed){longPressed=true;manageLaptop(laptop).catch(error=>setHomeStatus(error.message))}
    });
    button.addEventListener('click',()=>{
      if(!longPressed)connection.connect(laptop);
      longPressed=false;
    });
    list.appendChild(button);
  }
}
async function manageLaptop(laptop){
  const action=prompt(`For ${laptop.name}, type "rename" or "forget".`);
  if(action?.trim().toLowerCase()==='rename'){
    const name=prompt('Laptop name',laptop.name)?.trim();
    if(name){laptop.name=name;await saveLaptops();await renderLaptops()}
  }else if(action?.trim().toLowerCase()==='forget'&&confirm(`Forget ${laptop.name}?`)){
    if(activeLaptop?.id===laptop.id)connection.disconnect();
    await SecureStorage.remove(`secret:${laptop.id}`);
    laptops=laptops.filter(item=>item.id!==laptop.id);
    onlineIds.delete(laptop.id);
    await saveLaptops();
    await renderLaptops();
  }
}
function waitMessage(socket,timeout=5000){
  return new Promise((resolve,reject)=>{
    const cleanup=()=>{
      clearTimeout(timer);
      socket.removeEventListener('message',onMessage);
      socket.removeEventListener('close',onClose);
      socket.removeEventListener('error',onError);
    };
    const onMessage=event=>{cleanup();try{resolve(JSON.parse(event.data))}catch(error){reject(error)}};
    const onClose=event=>{
      cleanup();
      reject(new Error(event.code===4401?'Laptop rejected this phone.':'Laptop closed the connection during authentication.'));
    };
    const onError=()=>{cleanup();reject(new Error('WebSocket error during authentication.'))};
    const timer=setTimeout(()=>{cleanup();reject(new Error('Timed out waiting for laptop authentication.'))},timeout);
    socket.addEventListener('message',onMessage);
    socket.addEventListener('close',onClose);
    socket.addEventListener('error',onError);
  });
}
function openSocket(host,port){
  return new Promise((resolve,reject)=>{
    let settled=false;
    const socket=new WebSocket(`ws://${host}:${port}/ws`);
    const timer=setTimeout(()=>{
      if(!settled){settled=true;socket.close();reject(new Error(`Connection to ${host} timed out.`))}
    },2500);
    socket.addEventListener('open',()=>{
      if(!settled){settled=true;clearTimeout(timer);resolve(socket)}
    },{once:true});
    socket.addEventListener('error',()=>{
      if(!settled){settled=true;clearTimeout(timer);reject(new Error(`Could not connect to ${host}.`))}
    },{once:true});
  });
}
function bytesFromHex(hex){return new Uint8Array(hex.match(/.{2}/g).map(byte=>parseInt(byte,16)))}
function toHex(bytes){return [...new Uint8Array(bytes)].map(byte=>byte.toString(16).padStart(2,'0')).join('')}
async function makeMac(secret,nonce){
  const key=await crypto.subtle.importKey('raw',bytesFromHex(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  return toHex(await crypto.subtle.sign('HMAC',key,new TextEncoder().encode(nonce)));
}
class Connection{
  constructor(){this.stopped=true;this.expired=false;this.retrying=false;this.laptop=null;this.retryIndex=0}
  async connect(laptop,pairCode=null){
    this.stopped=false;this.expired=false;this.retryIndex=0;this.laptop=laptop;
    showControls(laptop);
    setConnectionStatus(false,'Connecting…');
    try{
      await KeepAwake.keepAwake();
      await ScreenOrientation.unlock();
    }catch(error){console.error('Could not enable control-screen device settings:',error)}
    try{
      await this.establish(pairCode);
      return true;
    }catch(error){
      if(this.stopped)return;
      this.stopped=true;
      console.error('Laptop connection failed:',error);
      await showHome();
      setHomeStatus(error.message);
      return false;
    }
  }
  async establish(pairCode=null){
    const hosts=[...new Set([this.laptop.host,this.laptop.lastHost].filter(Boolean))];
    let lastError=new Error('No laptop address is available.');
    for(const host of hosts){
      let socket;
      try{
        socket=await openSocket(host,this.laptop.port);
        let secret;
        if(pairCode){
          const deviceId=await getDeviceId();
          socket.send(JSON.stringify({t:'pair',code:pairCode,device_id:deviceId,device_name:'AirControl phone'}));
          const paired=await waitMessage(socket);
          if(paired.t!=='paired'||typeof paired.secret!=='string')throw new Error('Laptop refused pairing.');
          secret=paired.secret;
          await SecureStorage.set(`secret:${this.laptop.id}`,secret);
          const ready=await waitMessage(socket);
          if(ready.t!=='ok')throw new Error('Laptop did not complete pairing.');
        }else{
          const secretValue=await SecureStorage.get(`secret:${this.laptop.id}`);
          if(typeof secretValue!=='string')throw new Error('No saved pairing secret. Scan the laptop QR code again.');
          socket.send(JSON.stringify({t:'hello',device_id:await getDeviceId()}));
          const challenge=await waitMessage(socket);
          if(challenge.t!=='challenge'||typeof challenge.nonce!=='string')throw new Error('Laptop sent an invalid authentication challenge.');
          socket.send(JSON.stringify({t:'auth',mac:await makeMac(secretValue,challenge.nonce)}));
          const ready=await waitMessage(socket);
          if(ready.t!=='ok')throw new Error('Laptop rejected this phone.');
          secret=secretValue;
        }
        this.attach(socket,host);
        this.laptop.lastHost=host;
        this.laptop.lastUsed=Date.now();
        onlineIds.add(this.laptop.id);
        await saveLaptops();
        await renderLaptops();
        setConnectionStatus(true,`Connected to ${this.laptop.name}`);
        $('#reconnect-overlay').hidden=true;
        return;
      }catch(error){
        if(socket)socket.close();
        lastError=error;
        if(pairCode&&error.message.includes('refused'))continue;
        if(!pairCode&&error.message.includes('No saved pairing secret'))throw error;
        if(!pairCode&&error.message.includes('rejected'))throw error;
      }
    }
    throw lastError;
  }
  attach(socket,host){
    ws=socket;
    socket.addEventListener('message',event=>{
      let message;
      try{message=JSON.parse(event.data)}catch(error){console.error('Invalid message from laptop:',error);return}
      if(message.t==='expiring')$('#expiry-banner').hidden=false;
      if(message.t==='expired'){
        this.expired=true;
        this.stopped=true;
        socket.close();
        $('#expiry-banner').hidden=true;
        $('#reconnect-message').textContent='Session expired.';
        $('#manual-reconnect').hidden=false;
        $('#reconnect-overlay').hidden=false;
        setConnectionStatus(false,'Session expired');
      }
    });
    socket.addEventListener('close',()=>{
      if(ws===socket)ws=null;
      onlineIds.delete(this.laptop.id);
      renderLaptops();
      if(!this.stopped&&!this.expired)this.reconnect(host);
    });
  }
  async reconnect(host){
    if(this.retrying)return;
    this.retrying=true;
    const laptop=this.laptop;
    $('#reconnect-overlay').hidden=false;
    $('#manual-reconnect').hidden=true;
    $('#reconnect-message').textContent='Reconnecting…';
    setConnectionStatus(false,'Reconnecting…');
    while(!this.stopped&&!this.expired&&this.laptop===laptop){
      const delay=RETRY_DELAYS[Math.min(this.retryIndex++,RETRY_DELAYS.length-1)];
      await new Promise(resolve=>setTimeout(resolve,delay));
      if(this.stopped||this.expired)break;
      try{
        await this.establish();
        break;
      }catch(error){
        console.warn('Reconnect attempt failed:',error);
        if(error.message.includes('No saved pairing secret')||error.message.includes('rejected')){
          this.expired=true;this.stopped=true;
          $('#reconnect-message').textContent=error.message;
          $('#manual-reconnect').hidden=false;
          break;
        }
      }
    }
    this.retrying=false;
  }
  disconnect(){
    this.stopped=true;this.expired=false;this.retrying=false;
    if(ws){const socket=ws;ws=null;socket.close(1000,'phone disconnected')}
    if(this.laptop)onlineIds.delete(this.laptop.id);
    this.laptop=null;
    void showHome();
  }
}
const connection=new Connection();
async function getDeviceId(){
  let id=await preference('deviceId');
  if(!id){id=crypto.randomUUID();await Preferences.set({key:'deviceId',value:id})}
  return id;
}
async function scanQr(){
  try{
    const permission=await BarcodeScanner.requestPermissions();
    if(permission.camera!=='granted'&&permission.camera!=='limited')throw new Error('Camera permission is required to scan a laptop QR code.');
    if(Capacitor.getPlatform()==='android')await ensureBarcodeModule();
    const {barcodes}=await BarcodeScanner.scan({formats:[BarcodeFormat.QrCode]});
    if(!barcodes.length)return;
    await pairFromData(barcodes[0].rawValue);
  }catch(error){
    setScannerProgress('');
    const message=error.message.startsWith('Scanner download failed.')
      ?error.message
      :`Could not scan or pair: ${error.message}`;
    showPairFallback(`${message} You can type the pairing JSON instead.`);
  }
}
async function ensureBarcodeModule(){
  const {available}=await BarcodeScanner.isGoogleBarcodeScannerModuleAvailable();
  if(available)return;
  setScannerProgress('Preparing the scanner… keep this screen open and stay online.');
  let listener;
  let timeout;
  let resolveInstallation;
  let rejectInstallation;
  try{
    const installed=new Promise((resolve,reject)=>{
      resolveInstallation=resolve;
      rejectInstallation=reject;
    });
    installed.catch(()=>{});
    timeout=setTimeout(()=>rejectInstallation(new Error('Scanner module installation timed out.')),5*60*1000);
    listener=await BarcodeScanner.addListener('googleBarcodeScannerModuleInstallProgress',event=>{
      switch(event.state){
        case GoogleBarcodeScannerModuleInstallState.PENDING:
          setScannerProgress('Preparing the scanner… keep this screen open and stay online.');
          break;
        case GoogleBarcodeScannerModuleInstallState.DOWNLOADING:
          setScannerProgress(`Downloading scanner module${event.progress==null?'…':` ${event.progress}%`}`);
          break;
        case GoogleBarcodeScannerModuleInstallState.INSTALLING:
          setScannerProgress('Finishing scanner setup…');
          break;
        case GoogleBarcodeScannerModuleInstallState.COMPLETED:
          resolveInstallation();
          break;
        case GoogleBarcodeScannerModuleInstallState.FAILED:
          rejectInstallation(new Error('Scanner module installation failed.'));
          break;
        case GoogleBarcodeScannerModuleInstallState.CANCELED:
          rejectInstallation(new Error('Scanner module installation was canceled.'));
          break;
        case GoogleBarcodeScannerModuleInstallState.DOWNLOAD_PAUSED:
          setScannerProgress('Scanner download paused. Check your internet connection.');
          break;
        default:
          setScannerProgress('Preparing the scanner… keep this screen open and stay online.');
      }
    });
    await BarcodeScanner.installGoogleBarcodeScannerModule();
    await installed;
    const verification=await BarcodeScanner.isGoogleBarcodeScannerModuleAvailable();
    if(!verification.available)throw new Error('Scanner module did not become available.');
  }catch(error){
    throw new Error('Scanner download failed. Connect to the internet and try again.',{cause:error});
  }finally{
    clearTimeout(timeout);
    await listener?.remove();
    setScannerProgress('');
  }
}
async function pairFromData(raw){
  let laptop;
  try{laptop=JSON.parse(raw)}
  catch{throw new Error('Pairing data must be valid JSON copied from the laptop pairing page.')}
  if(!laptop||typeof laptop!=='object'||laptop.v!==1||typeof laptop.id!=='string'||typeof laptop.name!=='string'||typeof laptop.host!=='string'||!Number.isInteger(laptop.port)||typeof laptop.code!=='string'){
    throw new Error('This is not a valid AirControl pairing QR code.');
  }
  const saved={id:laptop.id,name:laptop.name,host:laptop.host,port:laptop.port,lastHost:laptop.host};
  const index=laptops.findIndex(item=>item.id===saved.id);
  if(index<0)laptops.push(saved);else laptops[index]={...laptops[index],...saved};
  await saveLaptops();
  return await connection.connect(saved,laptop.code);
}
$('#scan-qr').addEventListener('click',()=>scanQr());
$('#bScan').addEventListener('click',()=>{showBar();scanQr()});
$('#type-code-toggle').addEventListener('click',()=>showPairFallback());
$('#pair-cancel').addEventListener('click',()=>{$('#pair-fallback').hidden=true});
$('#pair-submit').addEventListener('click',async()=>{
  try{
    const connected=await pairFromData($('#pair-json').value.trim());
    if(connected){
      $('#pair-fallback').hidden=true;
      $('#pair-json').value='';
      $('#pair-error').textContent='';
    }else{
      $('#pair-error').textContent=$('#home-status').textContent||'Could not connect to the laptop.';
    }
  }catch(error){$('#pair-error').textContent=error.message}
});
$('#bConn').addEventListener('click',()=>connection.disconnect());
$('#bDisc').addEventListener('click',()=>connection.disconnect());
$('#stay').addEventListener('click',()=>{if(send({t:'renew'}))$('#expiry-banner').hidden=true});
$('#manual-reconnect').addEventListener('click',()=>{if(activeLaptop)connection.connect(activeLaptop)});
$('#cancel-reconnect').addEventListener('click',()=>connection.disconnect());
$('#auto-connect-toggle').addEventListener('change',event=>Preferences.set({key:'autoConnect',value:String(event.target.checked)}).catch(error=>setHomeStatus(error.message)));
function showBar(){
  const bar=$('#bar');bar.classList.add('show');clearTimeout(hideTimer);
  hideTimer=setTimeout(()=>bar.classList.remove('show'),4000);
}
$('#pill').addEventListener('click',showBar);
let edgeStart=null;
window.addEventListener('touchstart',event=>{edgeStart=event.touches[0].clientY<24?event.touches[0].clientY:null},{passive:true});
window.addEventListener('touchmove',event=>{if(edgeStart!==null&&event.touches[0].clientY-edgeStart>30){showBar();edgeStart=null}},{passive:true});
if(Capacitor.isNativePlatform())App.addListener('backButton',()=>showBar());
async function initialize(){
  await SecureStorage.setKeyPrefix('aircontrol');
  await loadLaptops();
  await renderLaptops();
  if($('#auto-connect-toggle').checked&&laptops.length){
    const last=[...laptops].sort((a,b)=>(b.lastUsed||0)-(a.lastUsed||0))[0];
    await connection.connect(last);
  }
}
initialize().catch(error=>setHomeStatus(`AirControl could not start: ${error.message}`));
function moveBy(dx,dy){
  carry.x+=dx;carry.y+=dy;
  const ix=Math.trunc(carry.x),iy=Math.trunc(carry.y);
  if(ix||iy){carry.x-=ix;carry.y-=iy;send({t:'move',dx:ix,dy:iy})}
}

// Tabs
$$('nav button').forEach(b=>b.onclick=()=>{
  $$('nav button').forEach(x=>x.classList.toggle('on',x===b));
  $$('.panel').forEach(p=>p.classList.toggle('show',p.id==='p-'+b.dataset.tab));
});

// Click buttons (hold = drag)
$$('[data-click]').forEach(b=>{
  b.addEventListener('pointerdown',e=>{e.preventDefault();b.classList.add('on');buzz();send({t:'down',b:b.dataset.click})});
  const up=()=>{if(b.classList.contains('on')){b.classList.remove('on');send({t:'up',b:b.dataset.click})}};
  b.addEventListener('pointerup',up);b.addEventListener('pointercancel',up);b.addEventListener('pointerleave',up);
});

// ---------- AIR MOUSE: tilt like a racing wheel ----------
const DEG=Math.PI/180;
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=v=>{const l=Math.hypot(v[0],v[1],v[2])||1;return [v[0]/l,v[1]/l,v[2]/l]};
const clamp1=x=>Math.max(-1,Math.min(1,x));

const ids=['sens','dead','max','curve','smooth','invx','invy'];
const cfg={};
function readCfg(){
  ids.forEach(id=>{
    const el=$('#'+id);
    cfg[id]=el.type==='checkbox'?el.checked:+el.value;
    const out=$('#o-'+id);
    if(out)out.textContent=id==='curve'?(cfg[id]/10).toFixed(1):cfg[id];
  });
  try{localStorage.setItem('aircfg',JSON.stringify(cfg))}catch(e){}
}
try{
  const s=JSON.parse(localStorage.getItem('aircfg')||'{}');
  ids.forEach(id=>{if(s[id]!=null){const el=$('#'+id);el.type==='checkbox'?el.checked=s[id]:el.value=s[id]}});
}catch(e){}
ids.forEach(id=>$('#'+id).addEventListener('input',readCfg));
readCfg();

class OneEuro{
  constructor(minCut=2.5,beta=0.04,dCut=1){this.minCut=minCut;this.beta=beta;this.dCut=dCut;this.x=null;this.dx=0}
  a(cut,dt){const tau=1/(2*Math.PI*cut);return 1/(1+tau/dt)}
  filter(x,dt){
    if(this.x==null){this.x=x;this.dx=0;return x}
    this.dx+=this.a(this.dCut,dt)*((x-this.x)/dt-this.dx);
    const cut=this.minCut+this.beta*Math.abs(this.dx);
    this.x+=this.a(cut,dt)*(x-this.x);
    return this.x;
  }
  reset(){this.x=null;this.dx=0}
}
const fRoll=new OneEuro(),fPitch=new OneEuro();

let UP=null;
window.addEventListener('deviceorientation',e=>{
  if(e.beta==null||e.gamma==null)return;
  const b=e.beta*DEG,g=e.gamma*DEG;
  UP=[-Math.cos(b)*Math.sin(g),Math.sin(b),Math.cos(b)*Math.cos(g)];
  tiltStep();
});

let aiming=false,held=false,allowed=false;
const T={fd:[0,1,0],sd:[1,0,0],last:0,ready:false};

async function ensureMotion(){
  if(allowed)return true;
  try{
    const req=[];
    if(typeof DeviceOrientationEvent!=='undefined'&&DeviceOrientationEvent.requestPermission)req.push(DeviceOrientationEvent.requestPermission());
    allowed=(await Promise.all(req)).every(r=>r==='granted');
    if(!req.length)allowed=true;
  }catch(e){allowed=false}
  if(!allowed)$('#aim').textContent='Motion access blocked. Allow it in browser settings and reload.';
  return allowed;
}
function tiltStart(){
  if(!UP)return;
  let fd=Math.abs(UP[2])>0.7?[0,1,0]:[0,0,-1];
  const k=dot(fd,UP);
  fd=norm([fd[0]-k*UP[0],fd[1]-k*UP[1],fd[2]-k*UP[2]]);
  T.fd=fd;T.sd=norm(cross(fd,UP));
  T.last=performance.now();T.ready=true;
  fRoll.reset();fPitch.reset();
}
function shape(a){
  const dead=cfg.dead,max=Math.max(cfg.max,dead+2),m=Math.abs(a);
  if(m<dead)return 0;
  return Math.sign(a)*Math.pow(Math.min((m-dead)/(max-dead),1),cfg.curve/10);
}
function tiltStep(){
  if(!aiming||!UP||!T.ready)return;
  const now=performance.now();
  const dt=Math.min(Math.max((now-T.last)/1000,0.001),0.05);T.last=now;
  fRoll.minCut=fPitch.minCut=10/cfg.smooth;
  const roll=fRoll.filter(-Math.asin(clamp1(dot(UP,T.sd)))/DEG,dt);
  const pitch=fPitch.filter(Math.asin(clamp1(dot(UP,T.fd)))/DEG,dt);
  const step=1400*(cfg.sens/14)*dt;
  moveBy((cfg.invx?-1:1)*shape(roll)*step,(cfg.invy?-1:1)*-shape(pitch)*step);
}

const aim=$('#aim');
const IDLE='Hold here and tilt the phone like a steering wheel';
aim.textContent=IDLE;
aim.addEventListener('pointerdown',async e=>{
  e.preventDefault();held=true;
  if(!(await ensureMotion())||!held)return;
  tiltStart();aiming=true;
  aim.classList.add('active');aim.textContent='Aiming…';buzz();
});
const stopAim=()=>{held=false;aiming=false;aim.classList.remove('active');if(allowed)aim.textContent=IDLE};
['pointerup','pointercancel','pointerleave'].forEach(ev=>aim.addEventListener(ev,stopAim));
$('#recenter').addEventListener('pointerdown',e=>{e.preventDefault();tiltStart();buzz()});
let sy=null;
$('#scroll').addEventListener('touchstart',e=>{sy=e.touches[0].clientY},{passive:true});
$('#scroll').addEventListener('touchmove',e=>{
  const y=e.touches[0].clientY,d=Math.round((y-sy)/14);
  if(d){send({t:'scroll',dy:d});sy=y}
},{passive:true});

// Touchpad
const pad=$('#pad');let pt=null;
pad.addEventListener('touchstart',e=>{
  e.preventDefault();
  pt={n:e.touches.length,max:e.touches.length,x:e.touches[0].clientX,y:e.touches[0].clientY,t:performance.now(),moved:0,sy:e.touches[0].clientY};
  pad.classList.add('active');
});
pad.addEventListener('touchmove',e=>{
  e.preventDefault();if(!pt)return;
  const t=e.touches[0],dx=t.clientX-pt.x,dy=t.clientY-pt.y;
  pt.max=Math.max(pt.max,e.touches.length);pt.moved+=Math.abs(dx)+Math.abs(dy);
  if(e.touches.length>=2){
    const s=Math.round((t.clientY-pt.sy)/10);
    if(s){send({t:'scroll',dy:s});pt.sy=t.clientY}
  }else{
    const g=1+Math.min(Math.hypot(dx,dy)/12,1.5);   // light acceleration
    moveBy(dx*1.4*g,dy*1.4*g);
  }
  pt.x=t.clientX;pt.y=t.clientY;
});
pad.addEventListener('touchend',e=>{
  e.preventDefault();
  if(pt&&e.touches.length===0){
    if(pt.moved<8&&performance.now()-pt.t<250){buzz();send({t:'click',b:pt.max>=2?'right':'left'})}
    pt=null;pad.classList.remove('active');
  }
});

// Keyboard
let mods=new Set();
function clearMods(){mods.clear();$$('[data-mod]').forEach(b=>b.classList.remove('on'))}
$$('[data-mod]').forEach(b=>b.onclick=()=>{
  const m=b.dataset.mod;mods.has(m)?mods.delete(m):mods.add(m);b.classList.toggle('on',mods.has(m));buzz();
});
function sendKey(k,extra=[]){send({t:'key',k,mods:[...new Set([...mods,...extra])]});clearMods()}
const fk=$('#fkeys');
for(let i=1;i<=12;i++){
  const b=document.createElement('button');
  b.textContent='F'+i;b.dataset.k='f'+i;
  b.onclick=()=>{buzz();sendKey('f'+i)};
  fk.appendChild(b);
}
$('#fn').onclick=()=>{fk.hidden=!fk.hidden;$('#fn').classList.toggle('on',!fk.hidden)};
$$('#keys button').forEach(b=>b.onclick=()=>{buzz();sendKey(b.dataset.k,b.dataset.m?[b.dataset.m]:[])});
const kbd=$('#kbd'),SENT='\u200b\u200b';   // sentinel so backspace is detectable on an "empty" box
function reset(){kbd.value=SENT;kbd.setSelectionRange(2,2)}
function onType(){
  const v=kbd.value;
  if(v.length<SENT.length)sendKey('backspace');
  else if(v.length>SENT.length){
    const s=v.slice(SENT.length).replace(/\n/g,'');
    if(v.includes('\n'))sendKey('enter');
    if(s){mods.size&&s.length===1?sendKey(s):send({t:'text',s})}
  }
  reset();
}
kbd.addEventListener('focus',()=>{if(!kbd.value)reset()});
kbd.addEventListener('input',e=>{if(!e.isComposing)onType()});
kbd.addEventListener('compositionend',onType);
reset();
