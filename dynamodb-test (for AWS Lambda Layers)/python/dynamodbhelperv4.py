import boto3
import pandas as pd

class DynamoDBHelper:
    def __init__(self):
        self.client = boto3.client('dynamodb')#,endpoint_url="http://localhost:8000") 
    
    def setup(self):
        if 'attendance' not in self.client.list_tables()['TableNames']:        
            self.client.create_table(
                TableName='attendance',
                KeySchema=[
                    {
                        'AttributeName': 'date_attended',
                        'KeyType': 'HASH'  # Partition key
                    },
                    {
                        'AttributeName': 'name',
                        'KeyType': 'RANGE'  # Sort key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'date_attended',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'name',
                        'AttributeType': 'S'
                    },

                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 1,
                    'WriteCapacityUnits': 1
                }
            )
    
    # def add_item(self, item_text, owner):
    #     stmt = "INSERT INTO items VALUE {'owner': '" + '{}'.format(owner) + "', 'description': '" + '{}'.format(item_text) + "'}"
    #     self.client.execute_statement(Statement = stmt)

    # def delete_item(self, item_text, owner):
    #     stmt = "DELETE FROM items WHERE owner = '" + '{}'.format(owner) + "' AND description = '" + '{}'.format(item_text) + "'"
    #     self.client.execute_statement(Statement = stmt)

    # def get_items(self, owner):
    #     stmt = "SELECT description FROM items WHERE owner = '{}'".format(owner)
    #     result = pd.json_normalize(self.client.execute_statement(Statement = stmt)['Items'])
    #     return [x[0] for x in result.values]
    
    ## added functions
    def get_cell_groups(self):
        stmt = "SELECT cell_group FROM person"
        result = pd.json_normalize(self.client.execute_statement(Statement = stmt)['Items'])
        return list(set([x[0] for x in result.values]))

    def get_cell_members(self, cell_group):
        stmt = "SELECT name FROM person WHERE cell_group = '{}'".format(cell_group)
        result = pd.json_normalize(self.client.execute_statement(Statement = stmt)['Items'])
        return list(set([x[0] for x in result.values]))
    
    def get_alr_entered_cell_members(self, cell_group, event_type, date_attended):
        stmt = "SELECT name FROM attendance WHERE cell_group = '{}' and event_type = '{}' and date_attended = '{}'".format(cell_group, event_type, date_attended)
        result = pd.json_normalize(self.client.execute_statement(Statement = stmt)['Items'])
        return list(set([x[0] for x in result.values]))
    
    def get_alr_attended_cell_members(self, cell_group, event_type, date_attended):
        stmt = "SELECT name FROM attendance WHERE attendance_type = 'Present' and cell_group = '{}' and event_type = '{}' and date_attended = '{}'".format(cell_group, event_type, date_attended)
        result = pd.json_normalize(self.client.execute_statement(Statement = stmt)['Items'])
        return list(set([x[0] for x in result.values]))
    
    def get_alr_absentvalid_cell_members(self, cell_group, event_type, date_attended):
        stmt = "SELECT name FROM attendance WHERE attendance_type = 'Absent Valid' and cell_group = '{}' and event_type = '{}' and date_attended = '{}'".format(cell_group, event_type, date_attended)
        result = pd.json_normalize(self.client.execute_statement(Statement = stmt)['Items'])
        return list(set([x[0] for x in result.values]))
    
    def del_alr_attended_cell_members(self, name, cell_group, event_type, date_attended):
        stmt = "DELETE FROM attendance WHERE attendance_type = 'Present' and name = '{}' and cell_group = '{}' and event_type = '{}' and date_attended = '{}'".format(name, cell_group, event_type, date_attended)
        self.client.execute_statement(Statement = stmt)
    
    def del_alr_absentvalid_cell_members(self, name, cell_group, event_type, date_attended):
        stmt = "DELETE FROM attendance WHERE attendance_type = 'Absent Valid' and name = '{}' and cell_group = '{}' and event_type = '{}' and date_attended = '{}'".format(name, cell_group, event_type, date_attended)
        self.client.execute_statement(Statement = stmt)
    
    def add_attendance(self, cell_group, event_type, date_attended, name, attendance_type):
        stmt = "INSERT INTO attendance VALUE {'cell_group': '" + '{}'.format(cell_group) + "', 'event_type': '" + '{}'.format(event_type) + "', 'date_attended': '" + '{}'.format(date_attended) + "', 'name': '" + '{}'.format(name) + "', 'attendance_type': '" + '{}'.format(attendance_type) + "'}"
        self.client.execute_statement(Statement = stmt)

    def add_new_member(self, name, role, cell_group, telegram_id, birth_date):
        stmt = "INSERT INTO person VALUE {'name': '" + '{}'.format(name) + "', 'role': '" + '{}'.format(role) + "', 'cell_group': '" + '{}'.format(cell_group) + "', 'telegram_id': '" + '{}'.format(telegram_id) + "', 'birth_date': '" + '{}'.format(birth_date) + "'}"
        self.client.execute_statement(Statement = stmt)