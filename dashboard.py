import customtkinter as ctk
from PIL import Image
#main window opening
win=ctk.CTk()
win.geometry('1524x784+0+0')
#win.resizable(False,False)
win.grid_columnconfigure(0, weight=1)
win.grid_rowconfigure(0, weight=1)

#frame
fra=ctk.CTkFrame(win)
fra.grid(row=0,column=0,sticky='nsew')

fra.grid_columnconfigure(0,weight=0)
fra.grid_columnconfigure(1,weight=1)
fra.grid_rowconfigure(0,weight=1)

#getting the bg image
img = ctk.CTkImage(light_image=Image.open("dashtry.png"),size=(1524,784))
label = ctk.CTkLabel(fra, image=img,text='')
label.grid(row=0,column=0,columnspan=2,sticky='nsew')

#dashboard heading
dash=ctk.CTkLabel(fra,text='Dashboard',font=('Calibri',75,'bold'),fg_color='transparent',bg_color='transparent',text_color='#00ABFF')
dash.grid(row=0,column=0,sticky='n',pady=10)

#another frame inside fra for the buttons on left
sidebar=ctk.CTkFrame(fra,width=200, fg_color='#202020')
sidebar.grid(row=0, column=0, sticky='nsw')
sidebar.grid_propagate(False)
'''
blank=ctk.CTkFrame(fra,width=200,height=100,fg_color='#202020')
blank.grid(row=0,column=0,sticky='nw')
'''
bt1=ctk.CTkButton(sidebar,width=200,height=50,fg_color='#202020',hover_color='#FF8000',text='Income/Expense',text_color='white',font=('Calibri',15))
bt2=ctk.CTkButton(sidebar,width=200,height=50,fg_color='#202020',hover_color='#FF8000',text='Investments',text_color='white',font=('Calibri',15))
bt3=ctk.CTkButton(sidebar,width=200,height=50,fg_color='#202020',hover_color='#FF8000',text='Balance Management',text_color='white',font=('Calibri',15))
bt4=ctk.CTkButton(sidebar,width=200,height=50,fg_color='#202020',hover_color='#FF8000',text='Budget',text_color='white',font=('Calibri',15))
bt5=ctk.CTkButton(sidebar,width=200,height=50,fg_color='#202020',hover_color='#FF8000',text='Analytics',text_color='white',font=('Calibri',15))

bt1.grid(row=1,column=0,pady=(150,0))
bt2.grid(row=2,column=0,pady=0)
bt3.grid(row=3,column=0,pady=0)
bt4.grid(row=4,column=0,pady=0)
bt5.grid(row=5,column=0,pady=0)

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