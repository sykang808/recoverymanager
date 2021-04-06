from kafka import KafkaConsumer 
from kafka import KafkaProducer 
from json import loads 
from json import dumps 
import requests
import threading
import json
import random
BOOTSTRAP_SERVERS = ['b-2.microservice-kafka-2.6lxf1h.c6.kafka.us-west-2.amazonaws.com:9094','b-1.microservice-kafka-2.6lxf1h.c6.kafka.us-west-2.amazonaws.com:9094']

class RecoveryManager():
    producer = KafkaProducer(acks=0, compression_type='gzip',security_protocol="SSL" ,bootstrap_servers=BOOTSTRAP_SERVERS, value_serializer=lambda v: json.dumps(v, sort_keys=True).encode('utf-8')) 
    ret_fin = 0
    ret_message = ''

    def register_kafka_listener(self, topic):
        # Poll kafka
        def poll():
            # Initialize consumer Instance
            consumer = KafkaConsumer(topic, bootstrap_servers=BOOTSTRAP_SERVERS, auto_offset_reset='earliest', enable_auto_commit=True, 
                                        group_id='my-mc' )

            print("About to start polling for topic:", topic)
            consumer.poll(timeout_ms=6000)
            print("Started Polling for topic:", topic)
            for msg in consumer:
                self.kafka_listener(msg)
        print("About to register listener to topic:", topic)
        t1 = threading.Thread(target=poll)
        t1.start()
        print("started a background thread")

    def on_send_success(self, record_metadata):
        print("topic: %s" % record_metadata.topic)
        self.ret_fin = 200
        self.ret_message = "successkafkaproduct"

    def on_send_error(self, excp):
        print("error : %s" % excp)
        self.producer.flush() 
        self.ret_fin = 400
        self.ret_message = "failkafkaproduct"

    def sendkafka(self, topic,data, status):
        data['status'] = status
        self.producer.send( topic, value=data).add_callback(self.on_send_success).add_errback(self.on_send_error) 
        self.producer.flush() 


    def kafka_listener(self, data):
        #check product name
        json_data = json.loads(data.value.decode("utf-8"))
        status = json_data['status']
        print(json_data)
        if status == "fail-reduce-kafka-user" or status == "fail-lack-kafka-user" or status == "fail-kafka-user" or status == "fail-kafka-delivery" or status == "fail-kafka-credit":
            url= 'http://flask-product-restapi.flask-product-restapi/product/' + str( json_data['product_id'])
            r = requests.get( url )
            ret_json = json.loads(r.content)
            if r.status_code != 200:
                self.sendkafka("retrykafka", json_data, status)   
                return;      

            ret_json['count'] += json_data['count']
            ret_json = json.dumps(ret_json)
            r = requests.patch( url ,ret_json)     
            if r.status_code != 200:
                self.sendkafka("retrykafka", json_data, status)   
                return;      

        if status == "fail-kafka-delivery" or status == "fail-kafka-credit":
            url= 'http://flask-user-restapi:5050/user/' + str(json_data['customer_id'])       
            r = requests.get( url )
            if r.status_code != 200:
                self.sendkafka("retrykafka", json_data, status)   
                return;     
            t_count = json_data['count']
            t_price = json_data['price']
            ret_json['money'] += t_count * t_price
            ret_json = json.dumps(ret_json)
            r = requests.patch( url ,ret_json) 
            if r.status_code != 200:
                self.sendkafka("retrykafka", json_data, status)   
                return;     

        t_status = status.replace("fail","recovery")
        self.sendkafka("orderkafka", json_data, t_status)   
                    
            
            
        print( {'message': json_data }, self.ret_fin )
         

         
if __name__ == '__main__':
#    OrderManager.register_kafka_listener('orderkafka')
#   app.run(host="0.0.0.0", port=5052,debug=True)
    productmanager = RecoveryManager()
    productmanager.register_kafka_listener('recoverykafka')