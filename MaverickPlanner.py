# Include
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from tkcalendar import DateEntry
import sqlite3
import hashlib
from plyer import notification
import datetime
import time
import threading
from pynput import keyboard, mouse
import pandas as pd
import os

# Function Definitions
# Database setup
def setup_database():
    conn = sqlite3.connect('maverick_planner.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY,
                        type TEXT,
                        title TEXT,
                        description TEXT,
                        due_date TEXT,
                        priority TEXT
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user (
                        id INTEGER PRIMARY KEY,
                        username TEXT,
                        password TEXT
                    )''')
    conn.commit()
    conn.close()

setup_database()

# Function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Function to check if password exists
def password_exists():
    conn = sqlite3.connect('maverick_planner.db')
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM user WHERE username=?", ('admin',))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# Function to validate password
def validate_password(password):
    conn = sqlite3.connect('maverick_planner.db')
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM user WHERE username=?", ('admin',))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == hash_password(password)

# Function to set password
def set_password(password):
    conn = sqlite3.connect('maverick_planner.db')
    cursor = conn.cursor()
    hashed_password = hash_password(password)
    cursor.execute("INSERT INTO user (username, password) VALUES (?, ?)", ('admin', hashed_password))
    conn.commit()
    conn.close()

# Main Application
class MaverickPlannerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Maverick Planner")
        self.geometry("600x400")

        # Tabs
        self.tab_control = ttk.Notebook(self)
        self.personal_tab = ttk.Frame(self.tab_control)
        self.work_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.work_tab, text="Work Tasks")
        self.tab_control.add(self.personal_tab, text="Personal Tasks")
        self.tab_control.pack(expand=1, fill="both")

        # Work Tab
        self.create_task_manager(self.work_tab, "Work")

        # Personal Tab
        if password_exists():
            self.ask_for_password()
        else:
            self.set_initial_password()
        self.create_task_manager(self.personal_tab, "Personal")

    def ask_for_password(self):
        password = simpledialog.askstring("Password", "Enter the password to access Personal Tasks:", show='*')
        if not validate_password(password):
            messagebox.showerror("Error", "Incorrect password!")
            self.ask_for_password()

    def set_initial_password(self):
        password = simpledialog.askstring("Set Password", "Set a password for Personal Tasks:", show='*')
        confirm_password = simpledialog.askstring("Confirm Password", "Confirm your password:", show='*')
        if password == confirm_password:
            set_password(password)
            messagebox.showinfo("Success", "Password set successfully!")
        else:
            messagebox.showerror("Error", "Passwords do not match!")
            self.set_initial_password()

    def create_task_manager(self, tab, task_type):
        # Task List
        self.task_tree = ttk.Treeview(tab, columns=("Title", "Description", "Due Date", "Priority"), show='headings')
        self.task_tree.heading("Title", text="Title")
        self.task_tree.heading("Description", text="Description")
        self.task_tree.heading("Due Date", text="Due Date")
        self.task_tree.heading("Priority", text="Priority")
        self.task_tree.pack(expand=1, fill="both")

        # Buttons
        add_button = ttk.Button(tab, text="Add Task", command=lambda: self.add_task(task_type))
        add_button.pack(side=tk.LEFT)
        edit_button = ttk.Button(tab, text="Edit Task", command=lambda: self.edit_task(task_type))
        edit_button.pack(side=tk.LEFT)
        delete_button = ttk.Button(tab, text="Delete Task", command=self.delete_task)
        delete_button.pack(side=tk.LEFT)
        self.load_tasks(task_type)

    def load_tasks(self, task_type):
        self.task_tree.delete(*self.task_tree.get_children())
        conn = sqlite3.connect('maverick_planner.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE type=?", (task_type,))
        for row in cursor.fetchall():
            self.task_tree.insert('', 'end', values=(row[2], row[3], row[4], row[5]))
        conn.close()

    def add_task(self, task_type):
        TaskDialog(self, "Add Task", task_type)

    def edit_task(self, task_type):
        selected_item = self.task_tree.selection()
        if selected_item:
            item = self.task_tree.item(selected_item)
            title, description, due_date, priority = item['values']
            TaskDialog(self, "Edit Task", task_type, title, description, due_date, priority)

    def delete_task(self):
        selected_item = self.task_tree.selection()
        if selected_item:
            item = self.task_tree.item(selected_item)
            title = item['values'][0]
            conn = sqlite3.connect('maverick_planner.db')
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE title=?", (title,))
            conn.commit()
            conn.close()
            self.task_tree.delete(selected_item)

    def create_pomodoro_tab(self):
        pomodoro_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(pomodoro_tab, text="Pomodoro Timer")

        # Pomodoro Timer Widgets
        self.pomodoro_title_label = tk.Label(pomodoro_tab, text="Pomodoro Session Title")
        self.pomodoro_title_label.pack(pady=10)

        self.pomodoro_title_entry = tk.Entry(pomodoro_tab)
        self.pomodoro_title_entry.pack(pady=10)

        self.time_label = tk.Label(pomodoro_tab, text="25:00", font=("Helvetica", 48))
        self.time_label.pack(pady=20)

        self.start_button = ttk.Button(pomodoro_tab, text="Start", command=self.start_pomodoro)
        self.start_button.pack(pady=5)

        self.stop_button = ttk.Button(pomodoro_tab, text="Stop", command=self.stop_pomodoro, state=tk.DISABLED)
        self.stop_button.pack(pady=5)

        self.reset_button = ttk.Button(pomodoro_tab, text="Reset", command=self.reset_pomodoro, state=tk.DISABLED)
        self.reset_button.pack(pady=5)

        self.is_running = False
        self.timer_thread = None
        self.pomodoro_time = 25 * 60

    def start_pomodoro(self):
        if not self.is_running:
            self.is_running = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.reset_button.config(state=tk.NORMAL)
            self.timer_thread = threading.Thread(target=self.run_pomodoro)
            self.timer_thread.start()

    def stop_pomodoro(self):
        if self.is_running:
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def reset_pomodoro(self):
        self.stop_pomodoro()
        self.pomodoro_time = 25 * 60
        self.update_timer_label()

    def run_pomodoro(self):
        while self.pomodoro_time > 0 and self.is_running:
            mins, secs = divmod(self.pomodoro_time, 60)
            self.time_label.config(text=f"{mins:02}:{secs:02}")
            time.sleep(1)
            self.pomodoro_time -= 1

        if self.pomodoro_time == 0:
            notification.notify(
                title=f"Pomodoro Session Complete: {self.pomodoro_title_entry.get()}",
                message="Time to take a break!",
                timeout=10
            )
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def update_timer_label(self):
        mins, secs = divmod(self.pomodoro_time, 60)
        self.time_label.config(text=f"{mins:02}:{secs:02}")

class TaskDialog(tk.Toplevel):
    def __init__(self, parent, title, task_type, task_title="", task_desc="", task_due_date="", task_priority="Low"):
        super().__init__(parent)
        self.title(title)
        self.task_type = task_type
        self.parent = parent

        # Title
        tk.Label(self, text="Title").pack()
        self.title_entry = tk.Entry(self)
        self.title_entry.insert(0, task_title)
        self.title_entry.pack()

        # Description
        tk.Label(self, text="Description").pack()
        self.desc_entry = tk.Entry(self)
        self.desc_entry.insert(0, task_desc)
        self.desc_entry.pack()

        # Due Date
        tk.Label(self, text="Due Date").pack()
        self.due_date_entry = DateEntry(self)
        self.due_date_entry.set_date(datetime.datetime.strptime(task_due_date, "%Y-%m-%d") if task_due_date else datetime.datetime.today())
        self.due_date_entry.pack()

        # Priority
        tk.Label(self, text="Priority").pack()
        self.priority_var = tk.StringVar(value=task_priority)
        priority_menu = ttk.Combobox(self, textvariable=self.priority_var, values=["Low", "Medium", "High"])
        priority_menu.pack()

        # Buttons
        save_button = ttk.Button(self, text="Save", command=self.save_task)
        save_button.pack(side=tk.LEFT)
        cancel_button = ttk.Button(self, text="Cancel", command=self.destroy)
        cancel_button.pack(side=tk.LEFT)

    def save_task(self):
        title = self.title_entry.get()
        description = self.desc_entry.get()
        due_date = self.due_date_entry.get_date().strftime("%Y-%m-%d")
        priority = self.priority_var.get()

        conn = sqlite3.connect('maverick_planner.db')
        cursor = conn.cursor()

        if self.title() == "Add Task":
            cursor.execute("INSERT INTO tasks (type, title, description, due_date, priority) VALUES (?, ?, ?, ?, ?)",
                           (self.task_type, title, description, due_date, priority))
        else:
            cursor.execute("UPDATE tasks SET description=?, due_date=?, priority=? WHERE title=?",
                           (description, due_date, priority, title))
        conn.commit()
        conn.close()

        self.parent.load_tasks(self.task_type)
        self.destroy()

# Reminder Functionality
def send_reminders():
    conn = sqlite3.connect('maverick_planner.db')
    cursor = conn.cursor()
    cursor.execute("SELECT title, due_date FROM tasks WHERE due_date=?", (datetime.date.today().strftime("%Y-%m-%d"),))
    tasks = cursor.fetchall()
    conn.close()

    for task in tasks:
        notification.notify(
            title=f"Task Due: {task[0]}",
            message=f"The task '{task[0]}' is due today.",
            timeout=10
        )

if __name__ == "__main__":
    send_reminders()
    app = MaverickPlannerApp()
    app.create_pomodoro_tab()
    app.mainloop()
