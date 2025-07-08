from flask import Flask, request, jsonify
from app import calculate_loan_api, main
from flasgger import Swagger, swag_from
from flask_cors import CORS
from utils import convert_df_fields

app = Flask(__name__)
CORS(app)  # 👈 Enables CORS for all routes
swagger = Swagger(app)


@app.route("/api", methods=["GET"])
def check_server():
    """Health check route
    ---
    responses:
      200:
        description: Server status
        schema:
          type: object
          properties:
            result:
              type: string
              example: Server is running
    """
    return jsonify({"result": "Server is running"})

@app.route("/api/calculate-loan", methods=["POST"])
@swag_from({
    'tags': ['Loan Calculation'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['months', 'payout', 'inception_date', 'bank'],
                'properties': {
                    'months': {'type': 'integer', 'example': 6},
                    'payout': {'type': 'string', 'example': "USDC"},
                    'inception_date': {'type': 'string', 'example': '2024-01-01'},
                    'bank': {'type': 'string', 'example': 'American Bank'}
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Loan calculation successful',
            'result': {
                'type': 'object',
                'properties': {
                    'aetherum_loan_details': {'type': 'string'},
                    'agent_response': {'type': 'string'},
                    'loan_metrics': {'type': 'string'}
                }
            }
        },
        400: {'description': 'Missing required fields'},
        500: {'description': 'Internal server error'}
    }
})
def calculate_loan():
    data = request.json
    months = data.get("months")
    payout = data.get("payout")
    inception_date = data.get("inception_date")
    bank = data.get("bank")
    totalPortfolioValue = data.get("totalPortfolioValue")
    listOfSelectedTokens = data.get("listOfSelectedTokens")


    if not all([totalPortfolioValue, listOfSelectedTokens, months, payout, inception_date, bank]):
        return jsonify({"error": "Missing required fields"}), 400

    result = calculate_loan_api(totalPortfolioValue, listOfSelectedTokens, months, payout, inception_date, bank)
    result = convert_df_fields(result)
    
    return jsonify({'description': 'Loan calculation successful', "result": result})

if __name__ == "__main__":
    app.run(port=5000)
