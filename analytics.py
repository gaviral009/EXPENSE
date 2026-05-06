import customtkinter as ctk
from PIL import Image
from sidebar import side
import matplotlib.pyplot as map
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

#main window opening
win=ctk.CTk()
win.geometry('1524x784+0+0')

#win.resizable(False,False)
win.grid_columnconfigure(0, weight=1)
win.grid_rowconfigure(0, weight=1)

fra=ctk.CTkFrame(win)
fra.grid(row=0,column=0,sticky='nsew')
#fra.grid_columnconfigure(0,weight=0)
fra.grid_columnconfigure(1,weight=1)
fra.grid_rowconfigure(0,weight=1)

side(fra)

an=ctk.CTkFrame(fra,width=1274,height=784)
an.grid(row=0,column=1,sticky='nsew')

Ana=ctk.CTkLabel(an,text='Analytics',text_color='white',font=('Algerian',50))
Ana.pack(pady=(70,30),anchor='nw',padx=50)

scroll=ctk.CTkScrollableFrame(an,width=1200,height=600)
scroll.pack()

g1=ctk.CTkFrame(scroll,width=200,height=200)
g1.pack(fill='both',padx=10,pady=10)
g1.pack_propagate(False)

fig,ax=map.subplots()

days=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
spend=[200,450,300,500,700,400,350]

ax.plot(days,spend, marker='m')
ax.set_title("Last 7 Days Spending")

canvas=FigureCanvasTkAgg(fig,master=g1)
canvas.draw()

canvas.get_tk_widget().pack(fill="both",expand=True)

win.mainloop()