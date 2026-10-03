import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="pnm1079"
)
cur=db.cursor()
cur.execute('create database if not exists Tracko')
cur.execute('use Tracko')
#cur.execute('create table if not exists loginpage()')
#cur.execute('create table if not exists ')
print("MySQL connected successfully!")
db.close()