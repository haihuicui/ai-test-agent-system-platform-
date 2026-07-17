import requests
import json

def do_auth():
    url = "https://xcloud-sit-15000.chromxhealth.com/api/auth/token/"
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
               "customerId": "1960631620761366529",
               "samplingSiteId": "1862049511997194242",
               "tdNumber": "555215",
               "barcode": "0715005",
               "testItemId": "2065318688096591874",
               "type": 1
           }
       ]
   }

   headers = {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + "fb4d6226-4453-44f5-b434-b1d88ae45ed4"
   }
   res = requests.request("POST", surl, headers=headers, json=sb).text
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
    print("-----------------------------------------------------")
    url3 = "https://xmetrix-sit-15000.chromxhealth.com/api/xmetrix-data/customer"
    body = {"name":"测试客户-1784256027786","description":"由自动化测试创建的客户","samplingSiteIds":["site-001"]}
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + "81d08712-4862-4478-b857-01478325f336"
    }
    res = requests.post(url=url3, json=body, headers=headers).text
    print(res)
