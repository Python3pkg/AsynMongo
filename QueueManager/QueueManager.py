#!/usr/bin/env python
# encoding: utf-8
# AUTHOR: XIANWU LIN
# EMAIL: linxianwusx@gmail.com
# TIME: 2016/3/4 14:30

'''
这个模块提供了一个OriginQueue类，扩展原生队列Queue。
提供了一个QueueManager类，管理队列，并提供http接口。
'''

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import urlparse
import threading
from PythonQueue import PythonQueue
try:
    import redis
    from redisQ import RedisQ
    redis_enable = True
except ImportError:
    redis_enable = False
try:
    import simplejson as json
except ImportError:
    import json

html_source = """
<html><head><meta charset="utf-8"><title>python原生队列监控</title><script type="text/javascript" src="http://cdn.hcharts.cn/jquery/jquery-1.8.3.min.js"></script><script type="text/javascript" src="http://cdn.hcharts.cn/highcharts/highcharts.js"></script></head><body><h1 style="text-align:center">python原生队列监控</h1><div id="control"></div><div id="container" style="width:800px;height:400px"></div><script>$(function(){$(document).ready(function(){function get_y(){var e=$("input[name='control']:checked").val();return $.getJSON("/qsize?name="+e,function(e){y_value=parseInt(e.qsize)}),y_value}function newCheck(){$.ajax({url:"/all_qsizes",dateType:"json",success:function(data){json=eval(data);var allSeriesId=new Array;$(chart.series).each(function(e,a){allSeriesId.push(a.options.id)});for(var jsonName=new Array,i=0;i<json.length;i++){jsonName.push(json[i].name);var name1=json[i].name,serie=chart.get(name1),x=(new Date).getTime(),y=json[i].qsize;-1!=$.inArray(name1,allSeriesId)?serie.addPoint([x,y],!1,!0):chart.addSeries({name:name1,id:name1,data:function(){for(var e=[],a=(new Date).getTime(),t=-24;0>=t;t++)e.push({x:a+1e3*t,y:0});return e[24][1]=y,e}()},!1)}for(var i=0;i<allSeriesId.length;i++)-1==$.inArray(allSeriesId[i],jsonName)&&chart.get(allSeriesId[i]).remove(!1);chart.redraw()}})}Highcharts.setOptions({global:{useUTC:!1}});var y_value=0;$("#container").highcharts({chart:{marginRight:120},title:{text:"队列大小实时监控"},xAxis:{type:"datetime",tickPixelInterval:150},yAxis:{title:{text:"数据量"},plotLines:[{value:0,width:1,color:"#808080"}]},tooltip:{backgroundColor:"#FCFFC5",borderColor:"black",borderRadius:10,formatter:function(){return"<b>"+this.series.name+"</b><br>"+Highcharts.dateFormat("%Y-%m-%d %H:%M:%S",this.x)+"<br>"+Highcharts.numberFormat(this.y,2)}},legend:{align:"right",verticalAlign:"top",layout:"vertical",floating:!0,x:0,y:100},exporting:{enabled:!1},credits:{enabled:!1},series:[]});var chart=$("#container").highcharts();setInterval(newCheck,1e3)})});</script></body></html>
"""

class RedisImportException(Exception):
    def __str__(self):
        return "can't import redis package, please install python-redis, you can use pip install redis"


# 单例模式
def singleton(_cls):
    inst = {}
    def getinstance(*args, **kwargs):
        if _cls not in inst:
            inst[_cls] = _cls(*args, **kwargs)
        return inst[_cls]
    return getinstance


#请求 对应队列的队列长度
#接口 /qsize?name=xxx  请求单个队列的长度
#接口 /all_qsize  请求全部队列的长度
#接口 / 请求监控首页
class HTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): #silent log out
        return

    def do_GET(self):
        self.protocal_version = "HTTP/1.1"
        path = urlparse.urlparse(self.path)
        if path.path == '/qsize':
            query = path.query.split("=")
            if len(query) == 2:
                if query[0].strip() == "name":
                    QM = QueueManager()
                    size = QM.qsize(query[1].strip())
                    self.send_response(200)
                    self.end_headers()
                    return_json = {
                        "name" : query[1].strip(),
                        "qsize" : str(size)
                        }
                    self.wfile.write(json.dumps(return_json))
        elif path.path == '/all_qsizes':
            QM = QueueManager()
            return_list = []
            for name in QM.all_queues().keys():
                json1 = {
                    "name" :  name,
                    "qsize" : QM.qsize(name)
                }
                return_list.append(json1)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(return_list))
        elif path.path == "/":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(html_source)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write("some wrong")

http_server = None

def start_server(host, port):
    global http_server
    print "http://%s:%d/ is open." % (host, port)
    http_server = HTTPServer((host, port), HTTPHandler)
    http_server.serve_forever() #设置一直监听并接收请求


@singleton
class QueueManager(object):
    def __init__(self, host='127.0.0.1', port=9999):
        self.queue_dict = dict()
        self.queue_name_counter = dict()
        self.service_running = False
        if not self.service_running:
            self.t = threading.Thread(target=start_server,args=(host, port))
            self.t.start()

    def Queue(self, queue_type="python_queue", name=None, **kwargs): #获取新队列或存在的队列
        if queue_type not in ["python_queue", "redis_queue"]: #入口检查
            raise Exception(queue_type + " wrong")
        if queue_type == "redis_queue" and redis_enable == False:
            raise RedisImportException

        if name in self.queue_dict.keys(): #存在队列即返回
            return self.queue_dict[name]
        else: #不存在队列即创建
            if not name: #默认的name为队列类型加递增值
                max_name_id = 0
                if self.queue_name_counter.has_key(queue_type):
                    name = queue_type + str(self.queue_name_counter[queue_type] + 1)
                    self.queue_name_counter[queue_type] += 1
                else:
                    name = queue_type + "0"
                    self.queue_name_counter[queue_type] = 0

            #实际添加队列到队列字典
            if queue_type == "python_queue":
                queue = PythonQueue(name, **kwargs)
            elif queue_type == "redis_queue":
                queue = RedisQ(name, **kwargs)
            self.queue_dict[name] = queue
            return queue

    def pull_redis_queue(self, host="localhost", port=6379, **kwargs): #拉取对应redis下的队列
        if not redis_enable:
            raise RedisImportException
        redis = redis.Redis(host = host, port = port, **kwargs)
        for key in redis.keys():
            if name[:11] == "redis_queue":
                self.queue_dict[key] = RedisQ(key, **kwargs)
                if self.queue_name_counter.has_key(queue_type):
                    self.queue_name_counter["redis_queue"] += 1
                else:
                    self.queue_name_counter["redis_queue"] = 0


    def all_queues(self): #获取全部队列字典
        return self.queue_dict

    def key(self, name): #返回队列名称
        if self.queue_dict.has_key(name):
            return self.queue.key()
        else:
            return None

    def remove(self, queue_object=None, name = None): #删除队列
        if (not queue_object) and (not name): #默认清空队列字典
            for queue in self.queue_dict.values():
                queue = None
            self.queue_dict = dict()
        elif queue_object in self.queue_dict.values(): #根据队列对象清除
            del self.queue_dict[queue_object.name]
        elif name in self.queue_dict.keys(): #根据队列名称清除
            del self.queue_dict[name]
        else:
            raise Exception("queue error")


    def qsize(self, name): #获取队列长度
        if self.queue_dict.has_key(name):
            return self.queue_dict[name].qsize()
        else:
            raise Exception("No queue %s" % name)

    def put_size(self, name): #获取put_size
        if self.queue_dict.has_key(name):
            return self.queue_dict[name].put_size()
        else:
            raise Exception("No queue %s" % name)

    def get_size(self, name): #获取put_size
        if self.queue_dict.has_key(name):
            return self.queue_dict[name].get_size()
        else:
            raise Exception("No queue %s" % name)


    def shutdown(self): #关闭队列的监控
        http_server.shutdown()

def main():
    import time
    QM = QueueManager()
    queue = QM.Queue(queue_type="python_queue")
    queue1 = QM.Queue(queue_type="redis_queue", host='10.67.2.245')
    queue1.put("asdf")
    queue1.put(123)
    queue.put(123)
    queue.put(123)
    time.sleep(3)
    queue.put(34)
    time.sleep(1)
    queue.put(34)
    time.sleep(0.1)
    queue.get()
    queue.get()
    time.sleep(2)
    queue.get()
    time.sleep(50)
    QM.shutdown()

if __name__ == '__main__':
    main()
