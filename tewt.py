import requests
import json

def do_auth():
    url = "https://xcloud-uat-15000.chromxhealth.com/api/auth/token/"
    user_name = "root"
    password = "$2b$12$VWqIzD.bmRdiG5L8aqcEE.PQivLEVPx7d5WdC/rhKGWCFwn2sI3ae"
    data = {
        "username": user_name,
        "password": password,
        "captcha": "8m3g"
    }

    resp = requests.post(url, json=data)
    resp_json = resp.json()

    token = resp_json["data"]["token"]
    print(resp_json)

    return token

token = do_auth()

def create_task_do():

   uurl = "https://xmetrix-uat-15000.chromxhealth.com/api/xmetrix-data/test-task"
   surl = "https://xmetrix-sit-15000.chromxhealth.com/api/xmetrix-data/test-task"



   ub = {
    "deviceSerialNumber": "BA23000029",
    "samples": [
        {
            "customerId": "2033718019950460929",
            "samplingSiteId": "2033717943689625601",
            "tdNumber": "789001",
            "barcode": "04",
            "testItemId": "2033718909767860226",
            "type": 1
        }
    ]
}
   sb = {
       "deviceSerialNumber": "BA23000029",
       "samples": [
           {
               "customerId": "2033718019950460929",
               "samplingSiteId": "2033717943689625601",
               "tdNumber": "789003",
               "barcode": "0002",
               "testItemId": "2075029943523377154",
               "type": 2
           }
       ]
   }

   headers = {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + "e17984c5-d4ff-4640-b4ea-17e5cc752f61"
   }
   res = requests.request("POST", uurl, headers=headers, json=ub).text
   print(res)
   # print(eval(res)['data'][0]['testTaskId'])


def zhichui():
   url = "https://xmetrix-uat-15000.chromxhealth.com/api/xmetrix-data/direct-task"
   body = {
    "deviceSerialNumber": "FDF3243434",
    "testItemId": "2020683005919526914",
    "userTestSubjectId": "2-2008440279092924417",
    "samplingSiteId":"1830532804868509697"
}
   headers = {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + "1b3170ac-26e3-4bc5-9202-12e826aa4f19"
   }

   res = requests.post(url=url, json=body, headers=headers).text
   print(res)


def zhichui2():
    # 测试环境
   url = "https://xmetrix-sit-15000.chromxhealth.com/api/xmetrix-data/direct-task"
   body = {
       "deviceSerialNumber": "FDF3243434",
       "testItemId": "2008438655856648193",
       "userTestSubjectId": "2-1970373602077638657",
       "samplingSiteId": "1826501989256364034"
   }
   headers = {
       'Content-Type': 'application/json',
       'Authorization': 'Bearer ' + "23dffc21-ec0a-4f4e-8bb8-5921a615c462"
   }

   res = requests.post(url=url, json=body, headers=headers).text
   print(res)

if __name__ == "__main__":
    create_task_do()
