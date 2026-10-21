import { createServer, request } from 'node:http';
import { spawn } from 'node:child_process';
import { createHmac, randomBytes } from 'node:crypto';
import { fixture } from './fixtures/crawler-report.mjs';
import { monitorFixture, documentFixture, attemptFixture } from './fixtures/crawler-monitor.mjs';
const secret = randomBytes(32).toString('hex'), key = randomBytes(32).toString('hex');
const payload = Buffer.from(JSON.stringify({ purpose:'session', exp:Math.floor(Date.now()/1000)+3600, id:12345, login:'preview-admin', name:'Test Preview' })).toString('base64url');
const token = payload + '.' + createHmac('sha256',secret).update(payload).digest('base64url');
const mock = createServer((req,res)=>{
  if(req.headers.authorization !== `Bearer ${key}`){res.writeHead(401);return res.end('{}');}
  const url = new URL(req.url,'http://localhost');
  res.setHeader('Content-Type','application/json');
  const data = url.pathname.endsWith('/report') ? fixture(Number(url.searchParams.get('days')||7)) : url.pathname.endsWith('/monitor') ? monitorFixture() : url.pathname.includes('/documents/') ? documentFixture() : attemptFixture();
  res.end(JSON.stringify(data));
});
mock.listen(3458,'127.0.0.1');
const child = spawn(process.execPath,['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','3459'],{windowsHide:true,stdio:['ignore','pipe','pipe'],env:{...process.env,NEXT_BUILD_DIR:'.next-crawler-monitor',ADMIN_APP_URL:'http://127.0.0.1:3457',ADMIN_SESSION_SECRET:secret,ADMIN_GITHUB_IDS:'12345',GITHUB_CLIENT_ID:'test',GITHUB_CLIENT_SECRET:'test',CRAWLER_REPORT_API_URL:'http://127.0.0.1:3458/admin/crawler/report',CRAWLER_REPORT_API_KEY:key}});
child.stdout.pipe(process.stdout);child.stderr.pipe(process.stderr);
const proxy = createServer((req,res)=>{
  if(req.url === '/__test_session'){res.writeHead(302,{'Set-Cookie':`de_admin_session=${token}; Path=/; HttpOnly; SameSite=Lax`,Location:'/admin/crawler'});return res.end();}
  const upstream = request({hostname:'127.0.0.1',port:3459,path:req.url,method:req.method,headers:req.headers},reply=>{res.writeHead(reply.statusCode,reply.headers);reply.pipe(res);});
  upstream.on('error',()=>{res.writeHead(503);res.end('Starting test preview');});req.pipe(upstream);
});
proxy.listen(3457,'127.0.0.1',()=>console.log('Synthetic test preview: http://127.0.0.1:3457/__test_session'));
function stop(){child.kill();mock.close();proxy.close();}
process.on('SIGINT',()=>{stop();process.exit();});process.on('SIGTERM',()=>{stop();process.exit();});
