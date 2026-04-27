import customtkinter as ctk
from PIL import Image
#main window opening
win=ctk.CTk()
win.geometry('1524x784+0+0')
#win.resizable(False,False)
win.grid_columnconfigure(0, weight=1)
win.grid_rowconfigure(0, weight=1)

#big frame
fra=ctk.CTkFrame(win)
fra.grid(row=0,column=0,sticky='nsew')

fra.grid_columnconfigure(0,weight=0)
fra.grid_columnconfigure(1,weight=1)
fra.grid_rowconfigure(0,weight=1)

#getting all the images here
trykare=ctk.CTkImage(dark_image=Image.open("wave.jpeg"),size=(1524,784)) #bg
#img = ctk.CTkImage(light_image=Image.open("dashbag.png"),size=(1524,784))
icon1=ctk.CTkImage(dark_image=Image.open("icon1.png"))#bt
icon2=ctk.CTkImage(dark_image=Image.open("icon2.png"))#bt
icon3=ctk.CTkImage(dark_image=Image.open("icon3.png"))#bt
icon4=ctk.CTkImage(dark_image=Image.open("icon4.png"))#bt
icon5=ctk.CTkImage(dark_image=Image.open("icon5.png"))#bt
logo=ctk.CTkImage(dark_image=Image.open("final logo.png"),size=(222,87))#logo

label = ctk.CTkLabel(fra, image=trykare,text='')
label.grid(row=0,column=0,columnspan=2,sticky='nsew')

#####have to use def function and connect to login ka page
nam1='Pratik'
nam='Hi '+nam1+'!'
hi=ctk.CTkLabel(label,text=nam,text_color='white',font=('Arial',50),fg_color='transparent',bg_color='transparent')
hi.grid(row=0,column=0,sticky='nw',padx=350,pady=70)

wlc=ctk.CTkLabel(fra,text='Welcome to',text_color='white',font=('Arial',70))

#another frame inside fra for the buttons on left
sidebar=ctk.CTkFrame(fra,width=250, fg_color='#202020')
sidebar.grid(row=0, column=0, sticky='nsw')
sidebar.grid_propagate(False)


#monthly n long term budget
visible=False
def showextra():
    global visible
    if not visible:
        bt4_1.grid(row=5,column=0,sticky='w')
        bt4_2.grid(row=6,column=0,sticky='w')
        bt4.configure(text='Budget                        ▼')
        visible=True
    else:
        bt4_1.grid_forget()
        bt4_2.grid_forget()
        bt4.configure(text='Budget                        ▶')
        visible=False

#logo
c=ctk.CTkLabel(sidebar,fg_color='#202020',width=250,height=200,text='',image=logo)
c.grid(row=0,column=0)
#all buttons
bt1=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#202020',hover_color='#FF8000',text='Income/Expense',text_color='white',font=('Calibri',20),anchor='w',image=icon1)
bt2=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#202020',hover_color='#FF8000',text='Investments',text_color='white',font=('Calibri',20),anchor='w',image=icon4)
bt3=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#202020',hover_color='#FF8000',text='Balance Management',text_color='white',font=('Calibri',20),anchor='w',image=icon3)
bt4=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#202020',hover_color='#FF8000',text='Budget                        ▶',text_color='white',font=('Calibri',20),anchor='w',image=icon5,command=showextra)
bt5=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#202020',hover_color='#FF8000',text='Analytics',text_color='white',font=('Calibri',20),anchor='w',image=icon2)
bt4_1=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#444444',hover_color='#FF8000',text='Monthly',text_color='white',anchor='w')
bt4_2=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#444444',hover_color='#FF8000',text='Long Term',text_color='white',anchor='w')

bt1.grid(row=1,column=0)
bt2.grid(row=2,column=0)
bt3.grid(row=3,column=0)
bt4.grid(row=4,column=0)
bt5.grid(row=5,column=0)

#for it to change colour when hovered
def onclick(event):
    event.widget.master.configure(text_color='black',fg_color='#FF8000')
def onleave(event):
    event.widget.master.configure(text_color='white',fg_color='#202020')
buttons=[bt1,bt2,bt3,bt4,bt5]
for i in buttons:
    i.bind('<Enter>',onclick)
    i.bind('<Leave>',onleave)



win.mainloop()