"https://hackernoon.com/learn-blockchains-by-building-one-117428612f46"
import time
import json
import hashlib
import requests
import threading
from uuid import uuid4
from urllib.parse import urlparse

from flask import Flask, jsonify, request


class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transaction = []
        self.new_block(previous_hash=1, proof=100)
        self.nodes = set()

    def new_block(self, proof, previous_hash=None):
        block = {
            "index": len(self.chain)+1,
            "timestamp": time.time(),
            "transaction": self.current_transaction,
            "proof": proof,
            "previous_hash": previous_hash or self.hash(self.chain[-1])
        }
        self.current_transaction=[]
        self.chain.append(block)
        return block

    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    @staticmethod
    def valid_proof(last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash.endswith("0000")

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print(f'\n----------\n')
            if block['previous_hash'] != self.hash(last_block):
                return False
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            last_block = block
            current_index += 1
        return True

    def resolve_conflict(self):
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain
        if new_chain:
            self.chain = new_chain
            return True
        return False

    def proof_of_work(self, last_proof):
        proof = 0
        while self.valid_proof(last_proof, proof) is None:
            proof += 1
        return proof

    def new_transaction(self, sender, recipient, amount):
        self.current_transaction.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })
        return self.last_block['index']+1

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]


app = Flask(__name__)

node_identifier = str(uuid4()).replace('-', '')
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)
    blockchain.new_transaction(sender="0",
                               recipient=node_identifier,
                               amount=1)
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)
    response = {
        "message": "New Block Forged",
        "index": block['index'],
        "transaction": block['transaction'],
        "proof": block['proof'],
        "previous_hash": block['previous_hash']
    }
    return jsonify(response)


@app.route("/transactions/new", methods=["POST"])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return "Missing values", 400
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route("/chain", methods=["GET"])
def full_chain():
    response = {
        "chain": blockchain.chain,
        "length": len(blockchain.chain)
    }
    return jsonify(response)


@app.route("/nodes/register", methods=['GET', 'POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get("nodes")
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        blockchain.register_node(node)
    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes)
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflict()
    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain was replaced',
            'chain': blockchain.chain
        }
    return jsonify(response), 200


if __name__ == "__main__":
    number_of_nodes = 5
    threads = []
    for i in range(number_of_nodes):
        threads.append(threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 5000+i}))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
