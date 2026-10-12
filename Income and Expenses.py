import customtkinter as ctk
from tkinter import messagebox
import mysql.connector as ms
con=ms.connect(host="localhost",user="root",password="pnm1079",database="tracko")
if con.is_connected():
    cur=con.cursor()
#main window opening
wiin=ctk.CTk()
wiin.geometry('1524x784+0+0')

#wiin.resizable(False,False)
wiin.grid_columnconfigure(0, weight=1)
wiin.grid_rowconfigure(0, weight=1)

fra=ctk.CTkFrame(wiin)
fra.grid(row=0,column=0,sticky='nsew')
fra.grid_columnconfigure(0,weight=1)
fra.grid_rowconfigure(0,weight=1)

ie=ctk.CTkFrame(fra,width=1274,height=784,fg_color='#1B1B1F')
ie.grid(row=0,column=0,sticky='nsew')

iebox=ctk.CTkFrame(ie,width=800,height=1000,fg_color='#2B2B2B')
iebox.grid(row=1,column=0,sticky='nsew',pady=(20,20),padx=50)
#iebox.pack(pady=(100,100),padx=50,anchor='nw')

InE=ctk.CTkLabel(ie,text='Income and Expenses',text_color='#F0EDE6',font=('Arial',50))
InE.grid(row=0,column=0,sticky='nsew',pady=(50,20))
#InE.pack(pady=(70,30),anchor='nw',padx=50)
#InE.pack(pady=(70,30),anchor='nw',padx=50)

#Income/Expense
row1 = ctk.CTkFrame(iebox,fg_color='#2B2B2B')
row1.pack(pady=(10,10),padx=50,anchor='nw')

incex=ctk.CTkLabel(row1,text='Income/Expense:               ',text_color='#F0EDE6',font=('Arial',25))
incex.grid(row=1,column=0,sticky='nsew')

incexd=ctk.CTkComboBox(row1,
    values=['Income','Expense'],
    width=250,
    height=40,
    corner_radius=8,
    fg_color="#202020",
    border_color="#555555",
    text_color="white",
    font=("Calibri", 16),
    button_color="#00A998",
    button_hover_color="#008F82",
    dropdown_fg_color="#202020",
    dropdown_text_color="white",
    dropdown_hover_color="#00A998",
    dropdown_font=("Calibri", 16))
incexd.grid(row=1,column=1,sticky='nsew')
#d1=incexd.get()

#Amount
rowa = ctk.CTkFrame(iebox,fg_color='#2B2B2B')
rowa.pack(pady=(10,10),padx=50,anchor='nw')

amt=ctk.CTkLabel(rowa,text='Amount:                            ',text_color='#F0EDE6',font=('Arial',25))
amt.grid(row=1,column=0,sticky='nsew')

amte=ctk.CTkEntry(rowa,placeholder_text='Enter Amount (₹)',width=250,height=40,corner_radius=8,fg_color="#202020",border_color="#555555")
amte.grid(row=1,column=1,sticky='nsew')

#Description
row2 = ctk.CTkFrame(iebox,fg_color='#2B2B2B')
row2.pack(pady=(10,10),padx=50,anchor='nw')

des=ctk.CTkLabel(row2,text='Description:                       ',text_color='#F0EDE6',font=('Arial',25))
des.grid(row=1,column=0,sticky='nsew')

dese=ctk.CTkEntry(row2,placeholder_text='Enter Description',width=250,height=40,corner_radius=8,fg_color="#202020",border_color="#555555")
dese.grid(row=1,column=1,sticky='nsew')

#Category
row3 = ctk.CTkFrame(iebox,fg_color='#2B2B2B')
row3.pack(pady=(10,10),padx=50,anchor='nw')

cat=ctk.CTkLabel(row3,text='Category:                           ',text_color='#F0EDE6',font=('Arial',25))
cat.grid(row=1,column=0,sticky='nsew')

catd=ctk.CTkComboBox(row3,values=['Essentials','Food','Healthcare','Travel','Shopping','Subscriptions','Education','Loans','Housing','Miscellaneous'],
    width=250,
    height=40,
    corner_radius=8,
    fg_color="#202020",
    border_color="#555555",
    text_color="white",
    font=("Calibri", 16),
    button_color="#00A998",
    button_hover_color="#008F82",
    dropdown_fg_color="#202020",
    dropdown_text_color="white",
    dropdown_hover_color="#00A998",
    dropdown_font=("Calibri", 16))
catd.grid(row=1,column=1,sticky='nsew')

#Mode of Payment
row4 = ctk.CTkFrame(iebox,fg_color='#2B2B2B')
row4.pack(pady=(10,10),padx=50,anchor='nw')

mod=ctk.CTkLabel(row4,text='Mode of Payment:              ',text_color='#F0EDE6',font=('Arial',25))
mod.grid(row=1,column=0,sticky='nsew')

modd=ctk.CTkComboBox(row4,values=['UPI','Cash','Debit Card','Credit Card','Net Banking','Cheque','EMI'],
    width=250,
    height=40,
    corner_radius=8,
    fg_color="#202020",
    border_color="#555555",
    text_color="white",
    font=("Calibri", 16),
    button_color="#00A998",
    button_hover_color="#008F82",
    dropdown_fg_color="#202020",
    dropdown_text_color="white",
    dropdown_hover_color="#00A998",
    dropdown_font=("Calibri", 16))
modd.grid(row=1,column=1,sticky='nsew')

#Date
row5 = ctk.CTkFrame(iebox,fg_color='#2B2B2B')
row5.pack(pady=(10,10),padx=50,anchor='nw')

dat=ctk.CTkLabel(row5,text='Date:(Date/Month/Year)     ',text_color='#F0EDE6',font=('Arial',25))
dat.grid(row=1,column=0,sticky='nsew')

day=ctk.CTkComboBox(row5,values=[str(i) for i in range(1, 32)],width=80,height=40,corner_radius=8,
    fg_color="#202020",
    border_color="#555555",
    text_color="white",
    font=("Calibri", 16),
    button_color="#00A998",
    button_hover_color="#008F82",
    dropdown_fg_color="#202020",
    dropdown_text_color="white",
    dropdown_hover_color="#00A998",
    dropdown_font=("Calibri", 16))
day.grid(row=1, column=1, padx=5)

month=ctk.CTkComboBox(row5,values=['1','2','3','4','5','6','7','8','9','10','11','12'],width=80,height=40,corner_radius=8,
    fg_color="#202020",
    border_color="#555555",
    text_color="white",
    font=("Calibri", 16),
    button_color="#00A998",
    button_hover_color="#008F82",
    dropdown_fg_color="#202020",
    dropdown_text_color="white",
    dropdown_hover_color="#00A998",
    dropdown_font=("Calibri", 16))
month.grid(row=1, column=2, padx=5)

year = ctk.CTkComboBox(row5,values=[str(i) for i in range(2025, 2031)],width=110,height=40,corner_radius=8,
    fg_color="#202020",
    border_color="#555555",
    text_color="white",
    font=("Calibri", 16),
    button_color="#00A998",
    button_hover_color="#008F82",
    dropdown_fg_color="#202020",
    dropdown_text_color="white",
    dropdown_hover_color="#00A998",
    dropdown_font=("Calibri", 16))
year.grid(row=1, column=3, padx=5)

#Joy Index Tracker
row6 = ctk.CTkFrame(iebox,fg_color='#2B2B2B')
row6.pack(pady=(10,10),padx=50,anchor='nw')

jit=ctk.CTkLabel(row6,text='Joy Index Tracker:             ',text_color='#F0EDE6',font=('Arial',25))
jit.pack(side='left',pady=10,anchor='nw')

jitd=ctk.CTkComboBox(row6,values=['1 (Least Joy)','2','3','4','5 (Most Joy)'],
    width=250,
    height=40,
    corner_radius=8,
    fg_color="#202020",
    border_color="#555555",
    text_color="white",
    font=("Calibri", 16),
    button_color="#00A998",
    button_hover_color="#008F82",
    dropdown_fg_color="#202020",
    dropdown_text_color="white",
    dropdown_hover_color="#00A998",
    dropdown_font=("Calibri", 16))
jitd.pack(padx=10,pady=10,anchor='nw')

jitdes=ctk.CTkLabel(row6,text='(How much Joy did this transaction give you on a scale of 1 to 5?)',text_color='#D2D2D2',font=('Arial',20))
jitdes.pack(side='left',padx=10,pady=(10,5),anchor='w')

def add_transaction():
    amount=float(amte.get())
    description=dese.get()
    category=catd.get()
    mode=modd.get()
    day_value=int(day.get())
    month_value=int(month.get())
    year_value=int(year.get())
    transaction_date="{}-{:02d}-{:02d}".format(year_value, month_value, day_value)
    joy=int(jitd.get()[0])
    cur.execute("select count(*) from ie")
    count=cur.fetchone()[0]
    slno=count+1

    query = """
    INSERT INTO ie (SlNo, amount, des, cat, mop, date, jit)
    VALUES ({}, {}, '{}', '{}', '{}', '{}', {})
    """.format(slno,amount,description,category,mode,transaction_date,joy)

    cur.execute(query)
    con.commit()
    messagebox.showinfo("Success", "Transaction added successfully!")
    print("Transaction added successfully!")

sub=ctk.CTkButton(iebox,text='Add transaction',fg_color='#00A998',text_color='white',width=250,height=50,font=('Arial',20),command=add_transaction)
sub.pack(pady=(10,10),padx=50,anchor='se')

wiin.mainloop()