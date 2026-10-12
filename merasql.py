import mysql.connector as ms

con=ms.connect(host="localhost",user="root",password="pnm1079",charset="utf8")
if con.is_connected():


    cur=con.cursor()
    cur.execute('create database if not exists Tracko')
    cur.execute('use Tracko')
    #cur.execute('create table if not exists loginpage()')
    #cur.execute('create table if not exists ')

    #Income and expenses
    cur.execute('create table if not exists ie(SlNo int primary key,amount float,des varchar(50),cat varchar(20),mop varchar(20),date date,jit int)')

    print("MySQL connected successfully!")
    cur.close()
    con.close()