import customtkinter as ctk
from PIL import Image
from sidebar import side

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

side(fra)

#getting all the images here
trykare=ctk.CTkImage(dark_image=Image.open("wave.jpeg"),size=(1274,784)) #bg
#img = ctk.CTkImage(light_image=Image.open("dashbag.png"),size=(1524,784))
wel=ctk.CTkImage(dark_image=Image.open("Welc.png"),size=(321,179))


intro=ctk.CTkFrame(fra,width=1274,height=784,fg_color='transparent',bg_color='transparent')
intro.grid(row=0,column=1,sticky='nsew')

label = ctk.CTkLabel(intro, image=trykare,text='')
label.place(relx=0,rely=0,relheight=1,relwidth=1)

act=ctk.CTkFrame(intro,width=1174,height=684)
act.place(x=50,y=50)

#####have to use def function and connect to login ka page
nam1='Pratik'
nam='Hi '+nam1+'!'
hi=ctk.CTkLabel(act,text=nam,text_color='#D7D7D7',font=('Segoe UI',40),fg_color='transparent',bg_color='transparent')
hi.place(x=50,y=20)

wlc=ctk.CTkLabel(act,image=wel,text='',fg_color='transparent',bg_color='transparent')
wlc.place(x=400,y=100)

bal=ctk.CTkButton(act,width=300,height=100,fg_color='#510000',text='Balance:\n₹0.00',text_color='white',font=('Calibri',30),hover_color='#C00000',border_color='#D7D7D7',border_width=1)
bal.place(x=80,y=300)

inc=ctk.CTkButton(act,width=300,height=100,fg_color='#002E05',text='Income:\n₹0.00',text_color='white',font=('Calibri',30),hover_color='#006B0E',border_color='#D7D7D7',border_width=1)
inc.place(x=430,y=300)

exp=ctk.CTkButton(act,width=300,height=100,fg_color='#001036',text='Expense:\n₹0.00',text_color='white',font=('Calibri',30),hover_color='#001F66',border_color='#D7D7D7',border_width=1)
exp.place(x=780,y=300)

win.mainloop()