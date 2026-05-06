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

maindict={200:'Mon',450:'Tue',300:'Wed',500:'Thu',700:'Fri',400:'Sat',350:'Sun'}

days=list(maindict.values())
spend=list(maindict.keys())

an=ctk.CTkFrame(fra,width=1274,height=784)
an.grid(row=0,column=1,sticky='nsew')

Ana=ctk.CTkLabel(an,text='Analytics',text_color='white',font=('Algerian',50))
Ana.pack(pady=(70,30),anchor='nw',padx=50)

scroll=ctk.CTkScrollableFrame(an,width=1200,height=600)
scroll.pack()
cards=ctk.CTkFrame(scroll,width=1200,height=120)
cards.pack()

a_text='Total Spent: ₹'+str(float(sum(spend)))
a=ctk.CTkLabel(cards,height=100,width=250,text=a_text,text_color='white',font=('Calibri',25),fg_color='#0B0D4D',corner_radius=6)
a.pack(padx=20,pady=20,side='left')

high=max(maindict)
b_text='Highest Spent On: '+str(maindict[high])
b=ctk.CTkLabel(cards,height=100,width=250,text=b_text,text_color='white',font=('Calibri',25),fg_color='#510000',corner_radius=6)
b.pack(padx=20,pady=20,side='left')

low=min(maindict)
c_text='Lowest Spent On: '+str(maindict[low])
c=ctk.CTkLabel(cards,height=100,width=250,text=c_text,text_color='white',font=('Calibri',25),fg_color='#002E05',corner_radius=6)
c.pack(padx=20,pady=20,side='left')

avg=sum(spend)/len(spend)
avgstr=str(round(avg,2))
d_text='Average Daily: ₹'+avgstr
d=ctk.CTkLabel(cards,height=100,width=250,text=d_text,text_color='white',font=('Calibri',25),fg_color='#660033',corner_radius=6)
d.pack(padx=20,pady=20,side='left')

g1=ctk.CTkFrame(scroll,width=1200,height=400)
g1.pack(fill='both',padx=10,pady=10)
g1.pack_propagate(False)

fig1,ax1=map.subplots()

ax1.plot(days,spend,color='#00E5FF',linestyle='-',marker='o')
ax1.set_title("Last 7 Days Expense",color='white',font='Calibri',fontsize=20)
ax1.set_xlabel("Date",color='#D7D7D7',fontsize=15)
ax1.set_ylabel("Expense",color='#D7D7D7',fontsize=15)
ax1.tick_params(axis='x',colors='white',labelsize=10)
ax1.tick_params(axis='y',colors='white',labelsize=10)
ax1.grid(True, linestyle='--', alpha=0.1, color='white')
ax1.patch.set_edgecolor('none')
ax1.patch.set_linewidth(0)
for sp in ax1.spines.values():
    sp.set_visible(False)

fig1.set_facecolor('#2B2B2B')
ax1.set_facecolor('#2B2B2B')

canvas1=FigureCanvasTkAgg(fig1,master=g1)
canvas1.draw()
canvas1.get_tk_widget().pack(fill='both',expand=True)

#10 criteria
criteria={'Travel':0,'Shopping':20,'Miscellaneous':10,'Subscriptions':10,'Essentials':10,'Healthcare':10,'Education':10,'Food':10,'Loans':10,'Housing':10}
cr=list(criteria.keys())
per=list(criteria.values())

g2=ctk.CTkFrame(scroll,width=600,height=400)
g2.pack(fill='both',padx=10,pady=10)
g2.pack_propagate(False)

qw=max(per)
explode=[0,0,0,0,0,0,0,0,0,0]
ma=per.index(qw)
explode[ma]=0.1
fig2,ax2=map.subplots()
ax2.pie(per,labels=None,wedgeprops=dict(edgecolor='#2B2B2B'),explode=explode,autopct='%1.1f%%',colors=['#A3F6DA','#FFB0B0','#FDFFB0','#BDDAFF','#95FF91','#D6B6FF','#FFE0B6','#FFC7E9','#E1E1E1','#FFCC99'])
ax2.legend(cr,loc='right')
fig2.set_facecolor('#2B2B2B')

canvas2=FigureCanvasTkAgg(fig2,master=g2)
canvas2.draw()
canvas2.get_tk_widget().pack(fill='both',expand=True,side='left')


win.mainloop()
