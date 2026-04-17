import customtkinter as ctk
from PIL import Image
#main window opening
win=ctk.CTk()
win.geometry('1524x784+0+0')
win.resizable(False,False)
win.grid_columnconfigure(0, weight=1)
win.grid_rowconfigure(0, weight=1)

#frame
fra=ctk.CTkFrame(win)
fra.grid(row=0,column=0,sticky='nsew')

#getting the bg image
img = ctk.CTkImage(light_image=Image.open("dashtry.png"),size=(1524,784))
label = ctk.CTkLabel(fra, image=img,text='')
label.grid(row=0,column=0,sticky='nsew')

#dashboard heading
dash=ctk.CTkLabel(fra,text='Dashboard',font=('Calibri',75,'bold'),fg_color='transparent',bg_color='transparent',text_color='#00ABFF')
dash.grid(row=0,column=0,sticky='n',pady=10)

#another frame inside fra for the buttons on left
sidebar=ctk.CTkFrame(fra, width=320, fg_color='transparent')
sidebar.grid(row=0, column=0, sticky='nw', padx=40, pady=120)

bt1=ctk.CTkButton(fra,width=300,height=75,fg_color='#FFA54A',hover_color='#FF8000',text='Income/Expense',text_color='black',font=('Calibri',30),corner_radius=0)
#bt1.grid(row=0,column=0,pady=100,padx=40,sticky='nw')

bt2=ctk.CTkButton(fra,width=300,height=75,fg_color='#FFA54A',hover_color='#FF8000',text='Investments',text_color='black',font=('Calibri',30),corner_radius=0)
#bt2.grid(row=0,column=0,pady=175,padx=40,sticky='nw')

bt3=ctk.CTkButton(fra,width=300,height=75,fg_color='#FFA54A',hover_color='#FF8000',text='Balance Management',text_color='black',font=('Calibri',30),corner_radius=0)
#bt3.grid(row=0,column=0,pady=250,padx=40,sticky='nw')

bt4=ctk.CTkButton(fra,width=300,height=75,fg_color='#FFA54A',hover_color='#FF8000',text='Budget',text_color='black',font=('Calibri',30),corner_radius=0)
#bt4.grid(row=0,column=0,pady=325,padx=40,sticky='nw')

bt5=ctk.CTkButton(fra,width=300,height=75,fg_color='#FFA54A',hover_color='#FF8000',text='Analytics',text_color='black',font=('Calibri',30),corner_radius=0)
#bt5.grid(row=0,column=0,pady=400,padx=40,sticky='nw')

bt1.grid(in_=sidebar, row=0, column=0, pady=5)
bt2.grid(in_=sidebar, row=1, column=0, pady=5)
bt3.grid(in_=sidebar, row=2, column=0, pady=5)
bt4.grid(in_=sidebar, row=3, column=0, pady=5)
bt5.grid(in_=sidebar, row=4, column=0, pady=5)
win.mainloop()