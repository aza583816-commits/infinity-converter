"""Isolated real Gunicorn/API pressure probe; never sends load to production."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import tempfile
import shutil
import time
import unicodedata
import urllib.error
import urllib.request

import pymupdf
from PIL import Image,ImageDraw


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scan',type=Path,required=True)
    parser.add_argument('--report-dir',type=Path,required=True)
    args=parser.parse_args();out=args.report_dir.resolve();out.mkdir(parents=True,exist_ok=False)
    temp=Path(tempfile.mkdtemp(prefix='infinity-pressure-',dir='/tmp'))
    with socket.socket() as bound:bound.bind(('127.0.0.1',0));port=bound.getsockname()[1]
    url=f'http://127.0.0.1:{port}'
    env=dict(os.environ,DATABASE_URL=f'sqlite:///{out}/accounts.db',TMPDIR=str(temp),
             ADMISSION_DIR=str(out/'admission'),PUBLIC_AUTH_ENABLED='0',PUBLIC_BILLING_ENABLED='0')
    sources=[]
    with pymupdf.open(args.scan) as original:
        for count in (12,10,8,6):
            source=out/f'scan-{count}.pdf'
            with pymupdf.open() as cut:cut.insert_pdf(original,to_page=count-1);cut.save(source)
            sources.append((source,count))
    image=Image.new('RGB',(2400,2100),'#265a8f');ImageDraw.Draw(image).rectangle((300,400,1800,1600),fill='#ecab36')
    picture=out/'image.bmp';image.save(picture);image.close()
    # Verify cleanup in both serving workers as well as the parent. Native
    # /tmp avoids the workspace filesystem inconsistencies seen in the probe.
    gunicorn_config=out/'probe_gunicorn.py'
    gunicorn_config.write_text("import json, os\nfrom pathlib import Path\n"
        "def worker_exit(server, worker):\n"
        "    count=len(list(Path(os.environ['TMPDIR']).glob('infinity-v7-*')))\n"
        "    print('INFINITY_PROBE_CLEANUP '+json.dumps({'worker':worker.pid,'workspaces':count}),flush=True)\n")
    log=(out/'server.log').open('w')
    process=subprocess.Popen([sys.executable,'-m','gunicorn','--config',str(gunicorn_config),'--bind',f'127.0.0.1:{port}',
        '--workers','2','--threads','2','--worker-tmp-dir','/dev/shm','--timeout','240','--access-logfile','-','--error-logfile','-',
        'app:app'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    measurements=[];stop=threading.Event()
    def sample():
        while not stop.wait(.2):
            records={}
            for path in Path('/proc').glob('[0-9]*/status'):
                try:
                    fields=dict(line.split(':',1) for line in path.read_text().splitlines() if ':' in line)
                    if os.readlink(path.parent/'ns/pid') != os.readlink('/proc/self/ns/pid'):continue
                    records[int(path.parent.name)]=(int(fields['PPid']),fields['Name'].strip(),int(fields.get('NSpid',str(path.parent.name)).split()[-1]))
                except (OSError,KeyError,ValueError):continue
            selected={pid for pid,entry in records.items() if entry[2]==process.pid}
            for _ in range(5):selected.update(pid for pid,(parent,_,_) in records.items() if parent in selected)
            pss=0
            for pid in selected:
                try:
                    for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
                        if line.startswith('Pss:'):pss+=int(line.split()[1]);break
                except OSError:pass
            measurements.append({'time':time.monotonic(),'pss_kib':pss,'tesseract_processes':sum(records.get(pid,(0,'',0))[1]=='tesseract' for pid in selected)})
    def get(path):
        started=time.monotonic()
        with urllib.request.urlopen(url+path,timeout=180) as response:body=response.read();status=response.status
        return {'status':status,'seconds':round(time.monotonic()-started,3),'body':json.loads(body)}
    def convert(tool,source,target):
        boundary='InfinitySyntheticPressureBoundary'
        body=b''
        for name,value in [('tool',tool),('param','ar+en')]:
            body+=f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        body+=f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{source.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+source.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
        request=urllib.request.Request(url+'/api/v2/convert',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
        started=time.monotonic()
        try:response=urllib.request.urlopen(request,timeout=240)
        except urllib.error.HTTPError as error:response=error
        with response:
            target.write_bytes(response.read());status=response.code;retry=response.headers.get('Retry-After')
        return {'tool':tool,'status':status,'seconds':round(time.monotonic()-started,3),'retry_after':retry,'output':target.name}
    report={'scope':'Local isolated Gunicorn 2 workers x 2 threads; real API/OCR, existing synthetic scanned fixtures. Not Railway capacity certification.','revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}
    try:
        deadline=time.monotonic()+30
        while True:
            try:get('/api/v2/readyz');break
            except (OSError,ValueError):
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        monitor=threading.Thread(target=sample);monitor.start()
        with ThreadPoolExecutor(max_workers=4) as pool:
            pending=[pool.submit(convert,'pdf-ocr',source,out/f'ocr-{count}.txt') for source,count in sources]
            time.sleep(.4)
            report['readyz_during_burst']=get('/api/v2/readyz')
            report['cheap_conversion_during_burst']=convert('image-to-png',picture,out/'image-output.png')
            results=[job.result() for job in pending]
        report['burst_results']=results
        retries=[]
        for (source,count),result in zip(sources,results):
            if result['status']==503:
                assert result['retry_after']=='3'
                retry=convert('pdf-ocr',source,out/f'ocr-{count}.txt');retries.append(retry)
                assert retry['status']==200,retry
            else:assert result['status']==200,result
            text=unicodedata.normalize('NFKC',(out/f'ocr-{count}.txt').read_text())
            for page in range(1,count+1):
                chunk=text.split(f'--- صفحة {page} ---',1)[1].split('--- صفحة ',1)[0]
                for line in (f'PAGE {page:03d} SAFETY INSPECTION',f'RECORD {page:05d} CODE 00123',f'AMOUNT {page*100}.50 SAR'):
                    assert line in chunk,(count,page,line,chunk)
                for word in ('فحص','معدات','السلامة'):assert word in chunk,(count,page,word,chunk)
        report['sequential_retry_results']=retries
        assert report['cheap_conversion_during_burst']['status']==200
        with Image.open(picture) as expected,Image.open(out/'image-output.png') as actual:
            assert expected.size==actual.size and expected.tobytes()==actual.tobytes()
        report['all_36_scanned_pages_exact_records_and_arabic_words_verified']=True
        report['image_pixels_identical']=True
        report['readyz_after_burst']=get('/api/v2/readyz')
        report['health_within_two_seconds']=report['readyz_during_burst']['seconds']<2
        report['cheap_conversion_within_two_seconds']=report['cheap_conversion_during_burst']['seconds']<2
    finally:
        stop.set()
        if 'monitor' in locals():monitor.join(3)
        report['peak_service_and_child_pss_kib']=max((r['pss_kib'] for r in measurements),default=0)
        report['peak_tesseract_processes']=max((r['tesseract_processes'] for r in measurements),default=0)
        os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(10)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        log.close()
        report['parent_namespace_workspaces_after_shutdown']=len(list(temp.glob('infinity-v7-*')))
        report['worker_namespace_cleanup']=[json.loads(line.split('INFINITY_PROBE_CLEANUP ',1)[1]) for line in (out/'server.log').read_text().splitlines() if line.startswith('INFINITY_PROBE_CLEANUP ')]
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        if report['parent_namespace_workspaces_after_shutdown']==0:shutil.rmtree(temp)
    assert report['health_within_two_seconds'],report['readyz_during_burst']
    assert report['cheap_conversion_within_two_seconds'],report['cheap_conversion_during_burst']
    assert report['peak_tesseract_processes']==1,report['peak_tesseract_processes']
    assert report['parent_namespace_workspaces_after_shutdown']==0,report['parent_namespace_workspaces_after_shutdown']
    assert len(report['worker_namespace_cleanup'])==2,report['worker_namespace_cleanup']
    assert all(item['workspaces']==0 for item in report['worker_namespace_cleanup']),report['worker_namespace_cleanup']
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
