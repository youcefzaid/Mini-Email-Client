import gi
import imaplib
import json
import ssl
import email
from email.header import decode_header
import threading
from gi.repository import GLib

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

# Load the configuration file
with open('config.json', 'r') as f:
    config = json.load(f)

def get_imap_settings(email):
    domain = email.split('@')[1]
    for entry in config:
        if domain in entry["Domains"]:
            return entry
    return None

class EmailClient(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="IMAP Email Client")
        self.set_default_size(800, 600)
        self.connect("destroy", Gtk.main_quit)
        
        # Dark theme
        self.get_style_context().add_class("dark")
        css = b"""
        .dark {
            background-color: #2E2E2E;
            color: #FFFFFF;
        }
        entry {
            background-color: #4E4E4E;
            color: #FFFFFF;
        }
        button {
            background-color: #4E4E4E;
            color: #FFFFFF;
        }
        """
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        # Create main layout
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(1000)
        self.add(self.stack)

        self.create_login_page()
        self.create_email_list_page()

    def create_login_page(self):
        login_grid = Gtk.Grid()
        login_grid.set_column_spacing(10)
        login_grid.set_row_spacing(10)
        
        self.email_entry = Gtk.Entry()
        self.password_entry = Gtk.Entry()
        self.password_entry.set_visibility(False)
        
        login_grid.attach(Gtk.Label(label="Email:"), 0, 0, 1, 1)
        login_grid.attach(self.email_entry, 1, 0, 1, 1)
        login_grid.attach(Gtk.Label(label="Password:"), 0, 1, 1, 1)
        login_grid.attach(self.password_entry, 1, 1, 1, 1)
        
        login_button = Gtk.Button(label="Login")
        login_button.connect("clicked", self.on_login_button_clicked)
        login_grid.attach(login_button, 1, 2, 1, 1)
        
        self.stack.add_named(login_grid, "login")

    def create_email_list_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        self.email_list_store = Gtk.ListStore(str, str, str)  # (Sender, Subject, Date)
        
        self.treeview = Gtk.TreeView(model=self.email_list_store)
        
        for i, column_title in enumerate(["Sender", "Subject", "Date"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)
        
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        scrolled_window.add(self.treeview)
        
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        
        self.prev_button = Gtk.Button(label="Previous")
        self.prev_button.connect("clicked", self.on_prev_button_clicked)
        button_box.pack_start(self.prev_button, True, True, 0)
        
        self.next_button = Gtk.Button(label="Next")
        self.next_button.connect("clicked", self.on_next_button_clicked)
        button_box.pack_end(self.next_button, True, True, 0)
        
        vbox.pack_start(scrolled_window, True, True, 0)
        vbox.pack_end(button_box, False, False, 0)
        
        self.stack.add_named(vbox, "email_list")
        
        self.email_list = []
        self.current_page = 0
        self.emails_per_page = 20

    def on_login_button_clicked(self, widget):
        email = self.email_entry.get_text()
        password = self.password_entry.get_text()
        settings = get_imap_settings(email)
        
        if settings:
            hostname = settings["Hostname"]
            port = settings["Port"]
            try:
                self.mail = imaplib.IMAP4_SSL(hostname, port)
                self.mail.login(email, password)
                print("Login successful")
                
                # Fetch emails in a separate thread
                self.fetch_thread = threading.Thread(target=self.fetch_emails)
                self.fetch_thread.start()
            except Exception as e:
                print(f"Login failed: {e}")
        else:
            print("Domain not supported")

    def fetch_emails(self):
        self.mail.select("inbox")
        result, data = self.mail.search(None, "ALL")
        email_ids = data[0].split()
        
        self.email_list = list(reversed(email_ids))
        
        # Ensure this runs on the main thread
        Gdk.threads_add_idle(GLib.PRIORITY_DEFAULT_IDLE, self.display_emails, self.current_page)

    def display_emails(self, page):
        self.email_list_store.clear()
        
        start = page * self.emails_per_page
        end = start + self.emails_per_page
        
        for i in range(start, min(end, len(self.email_list))):
            email_id = self.email_list[i]
            result, data = self.mail.fetch(email_id, '(RFC822)')
            msg = email.message_from_bytes(data[0][1])
            
            sender = decode_header(msg["From"])[0][0]
            subject = decode_header(msg["Subject"])[0][0]
            date = msg["Date"]
            
            if isinstance(sender, bytes):
                sender = sender.decode()
            if isinstance(subject, bytes):
                subject = subject.decode()
            
            self.email_list_store.append([sender, subject, date])
        
        self.prev_button.set_sensitive(page > 0)
        self.next_button.set_sensitive(end < len(self.email_list))

    def on_prev_button_clicked(self, widget):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_emails(self.current_page)

    def on_next_button_clicked(self, widget):
        if (self.current_page + 1) * self.emails_per_page < len(self.email_list):
            self.current_page += 1
            self.display_emails(self.current_page)

win = EmailClient()
win.show_all()
Gtk.main()
