import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, Gio

import sys
import imaplib
import json
import email
from email.header import decode_header
import threading
import re

# Retrieves IMAP settings for a given email address
def get_imap_settings(email):
    domain = email.split('@')[-1]
    
    try:
        with open('config.json', 'r') as config_file:
            config_data = json.load(config_file)
    except FileNotFoundError:
        print("Config file not found")
        return None
    except json.JSONDecodeError:
        print("Error decoding JSON from config file")
        return None

    for entry in config_data:
        if domain in entry.get("Domains", []):
            return {
                "Hostname": entry["Hostname"],
                "Port": entry["Port"],
                "SocketType": entry["SocketType"],
                "UserName": entry["UserName"].replace("%EMAILADDRESS%", email)
            }

    print(f"No configuration found for domain: {domain}")
    return None

class EmailClient(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Mini Email Client")
        self.set_default_size(800, 600)

        self.create_main_layout()
        self.create_login_page()
        self.create_email_list_page()
        self.create_email_content_page()

    # Creates the main layout stack
    def create_main_layout(self):
        self.stack = Gtk.Stack()
        self.set_child(self.stack)

    # Creates the login page UI
    def create_login_page(self):
        login_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        login_box.set_margin_top(48)
        login_box.set_margin_bottom(48)
        login_box.set_margin_start(24)
        login_box.set_margin_end(24)
        login_box.set_halign(Gtk.Align.CENTER)
        login_box.set_valign(Gtk.Align.CENTER)

        title_label = Gtk.Label(label="Sign in")
        title_label.get_style_context().add_class("title-1")
        login_box.append(title_label)

        self.login_entry = Gtk.Entry()
        self.login_entry.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
        self.login_entry.set_visibility(True)
        login_box.append(self.login_entry)

        self.login_button = Gtk.Button(label="Sign in")
        self.login_button.set_size_request(200, -1)
        self.login_button.get_style_context().add_class("suggested-action")
        self.login_button.connect("clicked", self.on_login_button_clicked)
        login_box.append(self.login_button)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(24, 24)

        self.error_label = Gtk.Label()
        self.error_label.get_style_context().add_class("error-message")
        self.error_label.set_visible(False)
        login_box.append(self.error_label)

        login_page = self.stack.add_child(login_box)
        login_page.set_name("login")

    # Creates the email list page UI
    def create_email_list_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_width_chars(30)
        search_box.append(self.search_entry)

        search_button = Gtk.Button(label="Search")
        search_button.get_style_context().add_class("suggested-action")
        search_button.connect("clicked", self.on_search_button_clicked)
        search_box.append(search_button)

        top_bar.append(search_box)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_bar.append(spacer)

        self.logout_button = Gtk.Button(label="Logout")
        self.logout_button.connect("clicked", self.on_logout_clicked)
        self.logout_button.set_visible(False)
        top_bar.append(self.logout_button)

        vbox.append(top_bar)

        self.email_list_store = Gtk.ListStore(str, str, str, str)
        self.treeview = Gtk.TreeView(model=self.email_list_store)
        self.treeview.get_style_context().add_class("email-list")

        columns = [
            ("Date", 150),
            ("Sender", 200),
            ("Subject", 400),
        ]

        for i, (title, width) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            column.set_resizable(True)
            column.set_fixed_width(width)
            column.set_sort_column_id(i)
            self.treeview.append_column(column)

        self.treeview.connect("row-activated", self.on_email_selected)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        scrolled_window.set_child(self.treeview)
        vbox.append(scrolled_window)

        pagination_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pagination_box.set_halign(Gtk.Align.CENTER)

        self.prev_button = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        self.prev_button.connect("clicked", self.on_prev_button_clicked)
        pagination_box.append(self.prev_button)

        self.page_label = Gtk.Label(label="Page 1")
        pagination_box.append(self.page_label)

        self.next_button = Gtk.Button.new_from_icon_name("go-next-symbolic")
        self.next_button.connect("clicked", self.on_next_button_clicked)
        pagination_box.append(self.next_button)

        vbox.append(pagination_box)

        email_list_page = self.stack.add_child(vbox)
        email_list_page.set_name("email_list")

        self.email_list = []
        self.current_page = 0
        self.emails_per_page = 20

    # Creates the email content page UI
    def create_email_content_page(self):
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)

        self.email_subject_label = Gtk.Label()
        self.email_subject_label.set_halign(Gtk.Align.START)
        self.email_subject_label.get_style_context().add_class("title-2")
        content_box.append(self.email_subject_label)

        self.email_info_label = Gtk.Label()
        self.email_info_label.set_halign(Gtk.Align.START)
        content_box.append(self.email_info_label)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)

        self.email_content_view = Gtk.TextView()
        self.email_content_view.set_editable(False)
        self.email_content_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        scrolled_window.set_child(self.email_content_view)

        content_box.append(scrolled_window)

        back_button = Gtk.Button(label="Back to Email List")
        back_button.connect("clicked", self.on_back_to_list_clicked)
        content_box.append(back_button)

        email_content_page = self.stack.add_child(content_box)
        email_content_page.set_name("email_content")

    # Handles login button click
    def on_login_button_clicked(self, widget):
        login_info = self.login_entry.get_text().strip()
        if ':' not in login_info:
            self.show_error("Invalid input format. Please use 'Email:Password'")
            return

        email, password = login_info.split(':', 1)
        settings = get_imap_settings(email)

        if settings:
            self.login_button.set_sensitive(False)
            self.login_button.set_child(self.spinner)
            self.spinner.start()
            self.error_label.set_visible(False)
            GLib.idle_add(self.connect_and_fetch_emails, email, password, settings)
        else:
            self.show_error(f"No IMAP settings found for email: {email}")

    # Connects to IMAP server and fetches emails
    def connect_and_fetch_emails(self, email, password, settings):
        try:
            hostname = settings["Hostname"]
            port = settings["Port"]
            self.mail = imaplib.IMAP4_SSL(hostname, port)
            self.mail.login(email, password)
            print("Login successful")

            self.fetch_emails()
            self.display_emails_and_update_ui(self.current_page)
            self.logout_button.set_visible(True)
        except imaplib.IMAP4.error as e:
            error_message = str(e)
            GLib.idle_add(self.show_error, f"Login failed: {error_message}")
        except Exception as e:
            GLib.idle_add(self.show_error, f"An error occurred: {str(e)}")
        finally:
            GLib.idle_add(self.reset_login_button)

    # Displays error message
    def show_error(self, message):
        self.error_label.set_text(message)
        self.error_label.set_visible(True)

    # Resets login button state
    def reset_login_button(self):
        self.login_button.set_sensitive(True)
        self.login_button.set_child(None)
        self.login_button.set_label("Sign in")
        self.spinner.stop()

    # Fetches emails from IMAP server
    def fetch_emails(self):
        self.mail.select("inbox")
        result, data = self.mail.search(None, "ALL")
        email_ids = data[0].split()
        self.email_list = list(reversed(email_ids))

    # Displays emails and updates UI
    def display_emails_and_update_ui(self, page):
        self.display_emails(page)
        self.stack.set_visible_child(self.stack.get_child_by_name("email_list"))

    # Displays emails for the current page
    def display_emails(self, page):
        self.email_list_store.clear()

        start = page * self.emails_per_page
        end = start + self.emails_per_page

        for i in range(start, min(end, len(self.email_list))):
            email_id = self.email_list[i]
            result, data = self.mail.fetch(email_id, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
            msg = email.message_from_bytes(data[0][1])

            date = self.parse_date(msg["Date"])
            sender = self.decode_header_field(msg["From"])
            subject = self.decode_header_field(msg["Subject"])

            self.email_list_store.append([date, sender, subject, email_id.decode()])

        self.prev_button.set_sensitive(page > 0)
        self.next_button.set_sensitive(end < len(self.email_list))
        self.page_label.set_text(f"Page {page + 1}")

    # Parses date string to a formatted date
    def parse_date(self, date_string):
        if isinstance(date_string, email.header.Header):
            date_string = str(date_string)
        try:
            parsed_date = email.utils.parsedate_to_datetime(date_string)
            return parsed_date.strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            return str(date_string)

    # Decodes email header fields
    def decode_header_field(self, field):
        decoded_parts = decode_header(field)
        decoded_field = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    decoded_part = part.decode(encoding or 'utf-8', errors='replace')
                except LookupError:
                    decoded_part = part.decode('utf-8', errors='replace')
            else:
                decoded_part = part
            decoded_field += decoded_part
        return decoded_field

    # Handles search button click
    def on_search_button_clicked(self, widget):
        search_text = self.search_entry.get_text().strip()
        if not search_text:
            return
        
        self.email_list_store.clear()
        
        widget.set_sensitive(False)
        spinner = Gtk.Spinner()
        spinner.start()
        widget.set_child(spinner)
        
        threading.Thread(target=self.perform_search, args=(search_text, widget), daemon=True).start()

    # Performs email search
    def perform_search(self, search_text, search_button):
        results = []
        search_pattern = re.compile(re.escape(search_text), re.IGNORECASE)
        
        for email_id in self.email_list:
            result, data = self.mail.fetch(email_id, '(RFC822)')
            raw_email = data[0][1]
            email_message = email.message_from_bytes(raw_email)

            date = self.parse_date(email_message["Date"])
            sender = self.decode_header_field(email_message["From"])
            subject = self.decode_header_field(email_message["Subject"])
            
            body = self.get_email_body(email_message)

            if (search_pattern.search(sender) or 
                search_pattern.search(subject) or 
                search_pattern.search(body)):
                results.append([date, sender, subject, email_id.decode()])

        GLib.idle_add(self.update_search_results, results, search_button)

    # Extracts email body
    def get_email_body(self, email_message):
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode(errors='ignore')
        else:
            return email_message.get_payload(decode=True).decode(errors='ignore')
        return "" 
    # Updates search results
    def update_search_results(self, results, search_button):
        for result in results:
            self.email_list_store.append(result)
        
        search_button.set_sensitive(True)
        search_button.set_child(None)
        search_button.set_label("Search")
        
        if not results:
            print("No results found")
        else:
            print(f"Found {len(results)} results")

    # Handles previous button click
    def on_prev_button_clicked(self, widget):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_emails(self.current_page)

    # Handles next button click
    def on_next_button_clicked(self, widget):
        if (self.current_page + 1) * self.emails_per_page < len(self.email_list):
            self.current_page += 1
            self.display_emails(self.current_page)

    # Handles email selection
    def on_email_selected(self, treeview, path, column):
        model = treeview.get_model()
        email_id = model[path][3]
        self.display_email_content(email_id)

    # Displays email content
    def display_email_content(self, email_id):
        result, data = self.mail.fetch(email_id, '(RFC822)')
        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email)

        subject = self.decode_header_field(email_message['Subject'])
        sender = self.decode_header_field(email_message['From'])
        date = self.parse_date(email_message['Date'])

        self.email_subject_label.set_text(subject)
        self.email_info_label.set_text(f"From: {sender}\nDate: {date}")

        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = email_message.get_payload(decode=True).decode()

        buffer = self.email_content_view.get_buffer()
        buffer.set_text(body)

        self.stack.set_visible_child_name("email_content")

    # Handles back to list button click
    def on_back_to_list_clicked(self, button):
        self.stack.set_visible_child_name("email_list")

    # Handles logout button click
    def on_logout_clicked(self, widget):
        if hasattr(self, 'mail'):
            try:
                self.mail.logout()
            except:
                pass
        self.email_list_store.clear()
        self.stack.set_visible_child_name("login")
        self.logout_button.set_visible(False)
        self.login_entry.set_text("")
        print("Logged out successfully")

app = Gtk.Application(application_id='com.example.emailclient')
app.connect('activate', lambda app: EmailClient(application=app).show())
app.run(sys.argv)