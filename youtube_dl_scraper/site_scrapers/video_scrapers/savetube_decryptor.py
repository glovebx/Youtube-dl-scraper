import json
import requests

# --- 配置 ---
# BASE_URL = "http://192.168.3.58:5000"
BASE_URL = "https://api.moco.co"
AUTH_KEY = "wordbento-alpha-test"

def call_savetube_decryptor(encrypted_data: str) -> dict:
    url = f"{BASE_URL}/savetube/decrypt"
    payload = {"encrypted_data": encrypted_data}

    session = requests.Session()
    
    # 设置公共请求头
    headers = {
        'Authorization': f'Wordbento-Auth-Key {AUTH_KEY}',
        'Accept': 'application/json',
        'Accept-Charset': 'UTF-8',
        'Content-Type': 'application/json'
    }    
    
    try:
        response = session.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()  # 检查HTTP错误状态
        
        data = response.json()
        print(f"成功解密数据 {data}")
        return data
        
    except requests.exceptions.RequestException as e:
        return None
    except json.JSONDecodeError as e:
        return None

# --- 示例调用 ---
if __name__ == "__main__":
    # 成功示例
    print("--- 运行成功示例 ---")
    data_to_send_success = "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"
    result_success = call_savetube_decryptor(data_to_send_success)
    print("Python 接收结果:")
    print(json.dumps(result_success, indent=2, ensure_ascii=False))

    print("\n" + "="*50 + "\n")

    # # 失败示例 (模拟 JS 内部抛出异常)
    # print("--- 运行失败示例 ---")
    # data_to_send_fail = "FAIL_DATA"
    # result_fail = call_js_decryptor(data_to_send_fail)
    # print("Python 接收结果:")
    # print(json.dumps(result_fail, indent=2, ensure_ascii=False))