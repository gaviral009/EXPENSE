import customtkinter as ctk
from PIL import Image
def side(parent):
    #fra=ctk.CTkFrame(parent)
    #fra.grid(row=0,column=0,sticky='nsew')
    icon1=ctk.CTkImage(dark_image=Image.open("icon1.png"))#bt
    icon2=ctk.CTkImage(dark_image=Image.open("icon2.png"))#bt
    icon3=ctk.CTkImage(dark_image=Image.open("icon3.png"))#bt
    icon4=ctk.CTkImage(dark_image=Image.open("icon4.png"))#bt
    icon5=ctk.CTkImage(dark_image=Image.open("icon5.png"))#bt
    logo=ctk.CTkImage(dark_image=Image.open("final logo.png"),size=(222,87))#logo


    sidebar=ctk.CTkFrame(parent,width=250, fg_color='#202020')
    sidebar.grid(row=0, column=0, sticky='nsw')
    sidebar.grid_propagate(False)

    #monthly n long term budget
    visible=False
    def showextra():
        nonlocal visible
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
    bt1=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#202020',hover_color='#00A998',text='Income/Expense',text_color='white',font=('Calibri',20),anchor='w',image=icon1)
    bt2=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#202020',hover_color='#00A998',text='Investments',text_color='white',font=('Calibri',20),anchor='w',image=icon4)
    bt3=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#202020',hover_color='#00A998',text='Balance Management',text_color='white',font=('Calibri',20),anchor='w',image=icon3)
    bt4=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#202020',hover_color='#00A998',text='Budget                        ▶',text_color='white',font=('Calibri',20),anchor='w',image=icon5,command=showextra)
    bt5=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#202020',hover_color='#00A998',text='Analytics',text_color='white',font=('Calibri',20),anchor='w',image=icon2)
    bt4_1=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#444444',hover_color='#00A998',text='   Monthly',text_color='white',anchor='w',font=('Calibri',16))
    bt4_2=ctk.CTkButton(sidebar,width=250,height=50,fg_color='#444444',hover_color='#00A998',text='   Long Term',text_color='white',anchor='w',font=('Calibri',16))

    bt1.grid(row=1,column=0)
    bt2.grid(row=2,column=0)
    bt3.grid(row=3,column=0)
    bt4.grid(row=4,column=0)
    bt5.grid(row=5,column=0)

    #for it to change colour when hovered
    def onclick(event):
        event.widget.configure(text_color='black',fg_color='#00A998')
    def onleave(event):
        event.widget.configure(text_color='white',fg_color='#202020')
    buttons=[bt1,bt2,bt3,bt4,bt5]
    for i in buttons:
        i.bind('<Enter>',onclick)
        i.bind('<Leave>',onleave)
    return sidebar