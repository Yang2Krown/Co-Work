// NODE_PATH or PLAYWRIGHT_MODULE may point to a local Playwright installation.
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';
const require = createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const directory=path.dirname(fileURLToPath(import.meta.url));
const browser=await chromium.launch({channel:'chrome', headless:true});
const page=await browser.newPage({viewport:{width:1440,height:960},deviceScaleFactor:1});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
for(const scene of ['empty','answer','agent','documents','compare','status']){
 await page.goto(pathToFileURL(path.join(directory,'index.html')).href+'#'+scene);
 await page.screenshot({path:path.join(directory,scene+'.png')});
 for(const viewport of [{width:1440,height:960},{width:1280,height:800}]){
  await page.setViewportSize(viewport);
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow)throw new Error(scene+' overflows '+viewport.width);
 }
 await page.setViewportSize({width:1440,height:960});
}
await page.goto(pathToFileURL(path.join(directory,'index.html')).href+'#empty');
await page.getByRole('button',{name:'建立我的知识库'}).click();
await page.waitForURL(/#documents$/);
if(errors.length)throw new Error(errors.join('\n'));
await browser.close();
console.log('Six PNGs rendered; six scenes checked at both sizes; navigation passed.');
