import boto3
import pandas as pd

class DynamoDBHelper:
    def __init__(self):
        self.client = boto3.client('dynamodb')#,endpoint_url="http://localhost:8000") 
    
    def setup(self):
        if 'items' not in self.client.list_tables()['TableNames']:        
            self.client.create_table(
                TableName='items',
                KeySchema=[
                    {
                        'AttributeName': 'owner',
                        'KeyType': 'HASH'  # Partition key
                    },
                    {
                        'AttributeName': 'description',
                        'KeyType': 'RANGE'  # Sort key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'owner',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'description',
                        'AttributeType': 'S'
                    },

                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 10,
                    'WriteCapacityUnits': 10
                }
            )
    
    def add_item(self, item_text, owner):
        stmt = "INSERT INTO items VALUE {'owner': '" + '{}'.format(owner) + "', 'description': '" + '{}'.format(item_text) + "'}"
        self.client.execute_statement(Statement = stmt)

    def delete_item(self, item_text, owner):
        stmt = "DELETE FROM items WHERE owner = '" + '{}'.format(owner) + "' AND description = '" + '{}'.format(item_text) + "'"
        self.client.execute_statement(Statement = stmt)

    def get_items(self, owner):
        stmt = "SELECT description FROM items WHERE owner = '{}'".format(owner)
        result = pd.json_normalize(self.client.execute_statement(Statement = stmt)['Items'])
        return [x[0] for x in result.values]