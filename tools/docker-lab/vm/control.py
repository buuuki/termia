import base64,json,socket,sys,time
mode=sys.argv[1]
sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
sock.settimeout(8)
sock.connect('/vm/qmp.sock' if mode=='qmp' else '/vm/guest-agent.sock')
stream=sock.makefile('rwb',buffering=0)
serial=0
def request(command,arguments=None):
 global serial
 serial+=1
 value={'execute':command,'id':serial}
 if arguments is not None: value['arguments']=arguments
 stream.write(json.dumps(value).encode()+b'\n')
 while True:
  row=stream.readline()
  if not row: raise RuntimeError('Control channel closed')
  reply=json.loads(row.lstrip(b'\xff'))
  if reply.get('id')==serial:
   if 'error' in reply: raise RuntimeError(str(reply['error']))
   return reply['return']
if mode=='qmp':
 greeting=json.loads(stream.readline())
 assert 'QMP' in greeting
 request('qmp_capabilities')
 print(json.dumps(request(sys.argv[2],json.loads(sys.argv[3]) if len(sys.argv)>3 else None)))
else:
 job=request('guest-exec',{'path':sys.argv[2],'arg':sys.argv[3:],'capture-output':True})
 deadline=time.monotonic()+45
 while True:
  status=request('guest-exec-status',{'pid':job['pid']})
  if status.get('exited'):
   for key in ('out-data','err-data'):
    if status.get(key): print(base64.b64decode(status[key]).decode(errors='replace'),end='')
   print('Guest exit:',status.get('exitcode',status.get('signal')))
   raise SystemExit(status.get('exitcode',1))
  if time.monotonic()>deadline: raise RuntimeError('Guest command exceeded deadline')
  time.sleep(.2)
