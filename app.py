from flask import Flask, render_template, request, jsonify
import requests
import time
import json
import os

app = Flask(__name__)

API_LOGIN = "https://simplix-integration.partner1.com.br/api/Login"
API_SIMULATE = "https://simplix-integration.partner1.com.br/api/Proposal/Simulate"

TOKEN = ""
TOKEN_EXPIRA = 0

def gerar_token():
    global TOKEN_EXPIRA
    try:
        dados = {
            "username": "477f702a-4a6f-4b02-b5eb-afcd38da99f8",
            "password": "b5iTIZ2n"
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        resp = requests.post(API_LOGIN, json=dados, headers=headers, timeout=10)
        if resp.status_code == 200 and resp.json().get("success"):
            token = resp.json()["objectReturn"]["access_token"]
            TOKEN_EXPIRA = time.time() + 3600 - 60
            print(f"[TOKEN] Gerado com sucesso")
            return token
    except Exception as e:
        print(f"Erro ao gerar token: {e}")
    return ""


def obter_token():
    global TOKEN
    if not TOKEN or time.time() >= TOKEN_EXPIRA:
        TOKEN = gerar_token()
    return TOKEN


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/consultar-cpf", methods=["POST"])
def consultar_cpf_unico():
    data = request.get_json()
    cpf = data.get("cpf", "").strip()
    tabela = data.get("tabela", "").strip() or "SX1"

    cpf = cpf.zfill(11)

    if not cpf or len(cpf) != 11 or not cpf.isdigit():
        return jsonify({"erro": "CPF inválido."}), 400

    for tentativa in range(5):
        resultado = consultar_cpf(cpf, tabela)
        if "limite" not in resultado["informacao"].lower():
            resultado["tabela"] = tabela  
            return jsonify(resultado)
        time.sleep(2)

    return jsonify({
        "cpf": cpf,
        "tabela": tabela,
        "saldoBruto": 0,
        "valorLiberado": 0,
        "situacao": "Erro",
        "informacao": "Limite de tentativas atingido após 5 tentativas",
        "final": True
    })

def consultar_cpf(cpf, tabela=None):
    payload = {
        "cpf": cpf, 
        "parcelas": 0, 
        "convenio": 1, 
        "produto": 1,
        "tabelaComercial": tabela
    }
    headers = {
        "Authorization": f"Bearer {obter_token()}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(API_SIMULATE, json=payload, headers=headers, timeout=60)
        txt = resp.text
        print(f"[{cpf}] 📡 Status Code: {resp.status_code}")

        try:
            data = resp.json()
            print(f"[{cpf}] RAW JSON:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
        except Exception:
            data = {}
            print(f"[{cpf}] RAW TEXT:\n{txt}")

        simulacoes = (data.get("objectReturn", {}) or {}).get("retornoSimulacao", [])

        if simulacoes:
            if tabela:
                filtradas = [
                    s for s in simulacoes
                    if s.get("tabelaCodigo") == tabela or s.get("tabelaTitulo") == tabela
                ]
                if filtradas:
                    sim = filtradas[0]
                else:
                    sim = simulacoes[0] 
            else:
                sim = simulacoes[0]

            detalhes = sim.get("detalhes", {}) or {}
            msg_ok = sim.get("mensagem", "") or "Autorizado"

            return {
                "cpf": cpf,
                "tabela": sim.get("tabelaCodigo") or sim.get("tabelaTitulo"),
                "saldoBruto": detalhes.get("saldoTotalBloqueado", 0),
                "valorLiberado": sim.get("valorLiquido", 0),
                "situacao": "Consulta OK",
                "informacao": msg_ok,
                "final": True
            }

        desc = (data.get("objectReturn", {}) or {}).get("description", "") or txt
        return {
            "cpf": cpf,
            "tabela": tabela,
            "saldoBruto": 0,
            "valorLiberado": 0,
            "situacao": "Erro",
            "informacao": desc,
            "final": True
        }

    except requests.exceptions.ReadTimeout:
        return {
            "cpf": cpf,
            "tabela": tabela,
            "saldoBruto": 0,
            "valorLiberado": 0,
            "situacao": "Erro",
            "informacao": "Timeout na API",
            "final": True
        }

    except Exception as e:
        return {
            "cpf": cpf,
            "tabela": tabela,
            "saldoBruto": 0,
            "valorLiberado": 0,
            "situacao": "Erro",
            "informacao": f"Erro inesperado: {e}",
            "final": True
        }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

