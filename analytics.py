import customtkinter as ctk
from PIL import Image
from sidebar import sideb
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

sideb(fra)

an=ctk.CTkFrame(fra,width=1274,height=784)
an.grid(row=0,column=1,sticky='nsew')

Ana=ctk.CTkLabel(an,text='Analytics',text_color='white',font=('Algerian',50))
Ana.pack(pady=(70,30),anchor='nw',padx=50)

scroll=ctk.CTkScrollableFrame(an,width=1200,height=600)
scroll.pack()

g1=ctk.CTkFrame(scroll,width=600,height=400)
g1.pack(fill='both',padx=10,pady=10,side='left')
g1.pack_propagate(False)

fig,ax=map.subplots()

days=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
spend=[200,450,300,500,700,400,350]

ax.plot(days,spend,color='#00E5FF',linestyle='-',marker='o')
ax.set_title("Last 7 Days Expense",color='white',font='Calibri',fontsize=20)
ax.set_xlabel("Date",color='#D7D7D7',fontsize=15)
ax.set_ylabel("Expense",color='#D7D7D7',fontsize=15)
ax.tick_params(axis='x',colors='white',labelsize=10)
ax.tick_params(axis='y',colors='white',labelsize=10)
ax.grid(True, linestyle='--', alpha=0.1, color='white')


fig.set_facecolor('#2B2B2B')
ax.set_facecolor('#2B2B2B')

canvas=FigureCanvasTkAgg(fig,master=g1)
canvas.draw()
canvas.get_tk_widget().pack(fill='both',expand=True)

win.mainloop()