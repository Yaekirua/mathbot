# -*- coding: utf-8 -*-

# Copyright (C) 2021-2023 Ilya Bezrukov, Stepan Chizhov, Artem Grishin
#
# This file is part of math_bot.
#
# math_bot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# any later version.
#
# math_bot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from io import StringIO

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,\
    InlineKeyboardMarkup, InlineKeyboardButton
from telebot.apihelper import ApiTelegramException

from git import Repo

from config import *
from logic import build_table
from matrix import Matrix, SizesMatchError, SquareMatrixRequired, NonInvertibleMatrix
from rings import *
from safe_eval import safe_eval, CalculationLimitError
from shunting_yard import InvalidSyntax, InvalidName, InvalidArguments
from statistics import log_function_call
from models import User, get_db, close_db, ReportRecord

bot = telebot.TeleBot(Config.BOT_TOKEN)

menu = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)  # this markup is bot menu
menu.add(KeyboardButton("/help"))

menu.add(KeyboardButton("/det"))
menu.add(KeyboardButton("/ref"))
menu.add(KeyboardButton("/m_inverse"))

menu.add(KeyboardButton("/factorize"))
menu.add(KeyboardButton("/euclid"))
menu.add(KeyboardButton("/idempotents"))
menu.add(KeyboardButton("/nilpotents"))
menu.add(KeyboardButton("/inverse"))
menu.add(KeyboardButton("/logic"))

menu.add(KeyboardButton("/calc"))
menu.add(KeyboardButton("/about"))

hide_menu = ReplyKeyboardRemove()  # sending this as reply_markup will close menu


def get_report_menu(user_id):
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton(text="Report a bug!", callback_data="report"))
    if user_id in Config.ADMINS:
        mk.add(InlineKeyboardButton(text="View errors", callback_data="view_reports"))
    return mk


def get_cancel_menu():
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton(text="Back", callback_data="cancel"))
    return mk


def get_type_report_menu(user_id):
    mk = InlineKeyboardMarkup(row_width=1)
    new_reports_button = InlineKeyboardButton(text="New bugs", callback_data="report_status_NEW")
    accepted_reports_button = InlineKeyboardButton(text="Accepted mistakes", callback_data="report_status_ACCEPTED")
    rejected_reports_button = InlineKeyboardButton(text="Rejected errors", callback_data="report_status_REJECTED")
    closed_reports_button = InlineKeyboardButton(text="Closed Bugs", callback_data="report_status_CLOSED")
    back_button = InlineKeyboardButton(text="Back", callback_data="back_button")
    if user_id in Config.ADMINS:
        mk.add(new_reports_button, accepted_reports_button, rejected_reports_button, closed_reports_button, back_button)
    return mk


def get_admin_menu(call):
    mk = InlineKeyboardMarkup(row_width=1)
    if call.data not in ["report_status_CLOSED", "report_status_REJECTED"] and call.from_user.id in Config.ADMINS:
        if call.data not in ["report_status_ACCEPTED"]:
            accept_report_button = InlineKeyboardButton(text="accept mistake", callback_data="accept_report")
            mk.add(accept_report_button)
        reject_report_button = InlineKeyboardButton(text="Reject error", callback_data="reject_report")
        close_report_button = InlineKeyboardButton(text="close error", callback_data="close_report")
        mk.add(reject_report_button, close_report_button)
        return mk


@bot.message_handler(commands=["start"])
def start_message(message):
    send_mess = (
        f"<b>Hello{ ', ' + message.from_user.first_name if message.from_user.first_name is not None else ''}!</b>\n"
        f"Use the keyboard or commands to call the desired chip\n"
        f"/help - call for help\n"
        f"/about - bot information\n"
        f"Our channel: {Config.CHANNEL_LINK}\n"
        )
    bot.send_message(message.chat.id, send_mess, parse_mode="html", reply_markup=menu)
    # User first-time creation
    db = get_db()
    User.get_or_create(db, message.from_user.id, message.from_user.last_name,
                       message.from_user.first_name, message.from_user.username)
    close_db()


@bot.message_handler(commands=["help"])
def send_help(message):
    inline_menu = get_report_menu(message.from_user.id)
    bot.send_message(message.chat.id,
                     ("<b>Matrix operations</b>\n"
                      "/det - determinant of a matrix.\n"
                      "/ref - row echelon form of a matrix (upper triangular).\n"
                      "/m_inverse - inverse of a matrix.\n"
                      "\n<b>Number theory and discrete mathematics</b>\n"
                      "/factorize - prime factorization of a natural number.\n"
                      "/euclid - GCD of two numbers and solution of Diophantine equation.\n"
                      "/idempotents - idempotent elements in Z/n.\n"
                      "/nilpotents - nilpotent elements in Z/n.\n"
                      "/inverse - inverse element in Z/n.\n"
                      "/logic - truth table of an expression.\n"
                      "\n<b>Calculators</b>\n"
                      "/calc - calculator for mathematical expressions.\n"
                      "\n<b>About this bot</b> /about\n"
                      ),
                     parse_mode="html", reply_markup=inline_menu)


@bot.message_handler(commands=["det"])
def det(message):
    m = bot.send_message(message.chat.id, "Enter the matrix: (in one message)", reply_markup=hide_menu)
    bot.register_next_step_handler(m, matrix_input, action="det")


@log_function_call("det")
def calc_det(message, action, matrix):
    try:
        result = matrix.det()
    except SquareMatrixRequired:
       bot.reply_to(message, "Determinant cannot be calculated for a non-square matrix!", reply_markup=menu)
    else:
        answer = str(result)
        bot.reply_to(message, answer, reply_markup=menu)
        return answer


@bot.message_handler(commands=["ref"])
def ref_input(message):
    m = bot.send_message(message.chat.id, "Enter the matrix: (in one message)", reply_markup=hide_menu)
    bot.register_next_step_handler(m, matrix_input, action="ref")


@log_function_call("ref")
def calc_ref(message, action, matrix):
    result = matrix.ref()
    answer = f"The matrix in row echelon form:\n<code>{str(result)}</code>"
    bot.send_message(message.chat.id, answer, parse_mode="html", reply_markup=menu)
    return answer


@bot.message_handler(commands=["m_inverse"])
def inv_input(message):
   m = bot.send_message(message.chat.id, "Enter the matrix: (in one message)", reply_markup=hide_menu)
   bot.register_next_step_handler(m, matrix_input, action="m_inverse")


@log_function_call("m_inverse")
def calc_inv(message, action, matrix):
    try:
        result = matrix.inverse()
    except NonInvertibleMatrix:
        bot.send_message(message.chat.id, "Inverse matrix does not exist!", reply_markup=menu)
        return
    else:
        answer = f"Inverse matrix:\n<code>{str(result)}</code>"
        bot.send_message(message.chat.id, answer, parse_mode="html", reply_markup=menu)
        return answer


action_mapper = {
    "det": calc_det,
    "ref": calc_ref,
    "m_inverse": calc_inv
}


def matrix_input(message, action):
    try:
        lst = [[float(x) for x in row.split()] for row in message.text.split("\n")]
        matrix = Matrix.from_list(lst)
    except SizesMatchError:
        bot.reply_to(message,
                     "Mismatch in row or column sizes. The matrix must be <b>rectangular</b>.",
                     reply_markup=menu,
                     parse_mode="html")
    except ValueError:
        bot.reply_to(message,
                     "Please enter a <b>numeric</b> square matrix.",
                     reply_markup=menu,
                     parse_mode="html")
    else:
        if matrix.n > Config.MAX_MATRIX:
            bot.reply_to(message, f"The matrix input has a limitation of {Config.MAX_MATRIX}x{Config.MAX_MATRIX}!",
                         reply_markup=menu)
        else:
            next_handler = action_mapper[action]
            next_handler(message, action=action, matrix=matrix)


@bot.message_handler(commands=["logic"])
def logic_input(message):
    m = bot.send_message(message.chat.id, "Enter a logical expression:",  # TODO: make logic operators description
                         reply_markup=hide_menu,
                         parse_mode="html")
    bot.register_next_step_handler(m, logic_output)


@log_function_call("logic")
def logic_output(message):
    try:
        table, variables = build_table(message.text)
        out = StringIO()  # abstract file (file-object)
        print(*variables, "F", file=out, sep=" " * 2)
        for row in table:
            print(*row, file=out, sep=" " * 2)
        answer = f"<code>{out.getvalue()}</code>"
        bot.send_message(message.chat.id, answer, parse_mode="html", reply_markup=menu)
        return answer
    except InvalidSyntax:
      bot.send_message(message.chat.id,  "Syntax error in the expression", reply_markup=menu)
    except InvalidName:
      bot.send_message(message.chat.id, "Unknown variable encountered", reply_markup=menu)
    except InvalidArguments:
      bot.send_message(message.chat.id, "Incorrect usage of the function", reply_markup=menu)
    except CalculationLimitError:
      bot.send_message(message.chat.id, "Reached the limit of computation complexity", reply_markup=menu)
    except ValueError:
      bot.send_message(message.chat.id, "Failed to recognize the value. Allowed values: 0, 1", reply_markup=menu)


@bot.message_handler(commands=["idempotents", "nilpotents"])
def ring_input(message):
    m = bot.send_message(message.chat.id, "Enter the ring modulus:")
    bot.register_next_step_handler(m, ring_output, command=message.text[1:])


@log_function_call("ring")
def ring_output(message, command):
    try:
        n = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "Input data error", reply_markup=menu)
        return
    if n >= Config.MAX_MODULO or n < 2:
        bot.send_message(message.chat.id, f"Limitation: 2 <= n < {Config.MAX_MODULO:E}", reply_markup=menu)
        return
    if command == "idempotents":
        result = [f"{row} -> {el}" for row, el in find_idempotents(n)]
        title = "Idempotents"
    elif command == "nilpotents":
        result = find_nilpotents(n)
        title = "Nilpotents"
    else:
        return
    if len(result) > Config.MAX_ELEMENTS:
        s = "There are too many elements to display..."
    else:
        s = "\n".join([str(x) for x in result])
    answer = (f"<b> {title} в Z/{n}</b>\n"
              f"Quantity: {len(result)}\n\n"
              f"{s}\n")
    bot.send_message(
        message.chat.id,
        answer,
        reply_markup=menu,
        parse_mode="html"
    )
    return answer


@bot.message_handler(commands=["inverse"])
def inverse_input_ring(message):
    m = bot.send_message(message.chat.id, "Enter the ring modulus:")
    bot.register_next_step_handler(m, inverse_input_element)


def inverse_input_element(message):
    try:
        n = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id,"Input data error", reply_markup=menu)
        return
    if n >= Config.MAX_MODULO or n < 2:
        bot.send_message(message.chat.id, f"Limitation: 2 <= n < {Config.MAX_MODULO:E}", reply_markup=menu)
        return
    m = bot.send_message(message.chat.id,"Enter the element for which you want to find the inverse:")
    bot.register_next_step_handler(m, inverse_output, modulo=n)


@log_function_call("inverse")
def inverse_output(message, modulo):
    try:
        n = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "Input data error", reply_markup=menu)
        return
    n = n % modulo
    try:
        result = find_inverse(n, modulo)
    except ArithmeticError:
        answer = (f"У {n} <b>There is no inverse in the ring Z./{modulo}\n"
                  f"As the GCD (Greatest Common Divisor)({n}, {modulo}) > 1")
        bot.send_message(message.chat.id, answer, parse_mode="html")
        return answer
    else:
        answer = str(result)
        bot.send_message(message.chat.id, answer)
        return answer


@bot.message_handler(commands=["factorize"])
def factorize_input(message):
    m = bot.send_message(message.chat.id, "Enter a number:")
    bot.register_next_step_handler(m, factorize_output)


@log_function_call("factorize")
def factorize_output(message):
    try:
        n = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "Input data error", reply_markup=menu)
        return
    if n < 2 or n > Config.FACTORIZE_MAX:
        bot.send_message(
            message.chat.id,
            f"Factorization is available for positive integers n: 2 <= n <= {Config.FACTORIZE_MAX:E}"
        )
    else:
        fn = factorize(n)
        answer = f"{n} = " + factorize_str(fn)
        bot.send_message(message.chat.id, answer)
        return answer


@bot.message_handler(commands=["euclid"])
def euclid_input(message):
    m = bot.send_message(message.chat.id, "Enter two numbers separated by a space:")
    bot.register_next_step_handler(m, euclid_output)


@log_function_call("euclid")
def euclid_output(message):
    try:
        a, b = map(int, message.text.strip().split(" "))
    except ValueError:
        bot.send_message(message.chat.id, "Input data error", reply_markup=menu)
        return
    d, x, y = ext_gcd(a, b)
    answer = (f"GCD (Greatest Common Divisor)({a}, {b}) = {d}\n\n"
              f"<u>Equation solution:</u>\n{a}*x + {b if b >= 0 else f'({b})'}*y <b>= {d}</b>\n"
              f"x = {x}\ny = {y}\n\n"
              "<u>Attention</u>\n"
              f"<b>Pay attention to the form of the equation!</b>\n"
              f"The equation of the form ax + by = GCD(a, b) is being solved!")
    bot.send_message(message.chat.id, answer, parse_mode="html")
    return answer


@bot.message_handler(commands=["calc"])
def calc_input(message):
    m = bot.send_message(message.chat.id, "Enter the expression:", parse_mode="html")
    bot.register_next_step_handler(m, calc_output)


@log_function_call("calc")
def calc_output(message):
    try:
        answer = str(safe_eval(message.text))
    except InvalidSyntax:
        bot.send_message(message.chat.id, "Syntax error in the expression", reply_markup=menu)
    except InvalidName:
        bot.send_message(message.chat.id, "Unknown variable encountered", reply_markup=menu)
    except InvalidArguments:
        bot.send_message(message.chat.id, "Incorrect usage of function")
    except CalculationLimitError:
        bot.send_message(message.chat.id, "Reached the limit of computation complexity", reply_markup=menu)
    except ZeroDivisionError:
        bot.send_message(message.chat.id, "During execution, division by zero was encountered", reply_markup=menu)
    except ArithmeticError:
        bot.send_message(message.chat.id, "Arithmetic error", reply_markup=menu)
    except ValueError:
        bot.send_message(message.chat.id, "Failed to recognize the value", reply_markup=menu)
    else:
        bot.send_message(message.chat.id, answer, parse_mode="html", reply_markup=menu)
        return answer


@bot.message_handler(commands=["broadcast", "bc"])
def broadcast_input(message):
    if message.from_user.id not in Config.ADMINS:
        return
    m = bot.send_message(message.chat.id, "Message for mailing:")
    bot.register_next_step_handler(m, broadcast)


def broadcast(message):
    db = get_db()
    blocked_count = 0
    for user in db.query(User).all():
        try:
            bot.send_message(user.id, message.text)
        except ApiTelegramException:
            blocked_count += 1
    bot.send_message(message.chat.id, "Mailing completed successfully!\n"
                                      f"The mailing was not received. {blocked_count}")
    close_db()


@bot.message_handler(commands=["about"])
def send_about(message):
    repo = Repo("./")
    version = next((tag for tag in repo.tags if tag.commit == repo.head.commit), None)
    warning = ""
    if not version:
        version = repo.head.commit.hexsha
        warning = " (<u>Unstable.</u>)"
    bot.send_message(message.chat.id,
                     f"Version.{warning}: <b>{version}</b>\n"
                     f"Our channel.: {Config.CHANNEL_LINK}\n"
                     f"\nCopyright (C) 2023 @hizalhaziq\n"
                     f"GitHub: {Config.GITHUB_LINK}\n"
                     "<b>Under GNU-GPL 2.0-or-later license</b>",
                     parse_mode="html")


@bot.callback_query_handler(func=lambda call: call.data == "report")
def callback_inline(call):
    mk = get_cancel_menu()
    m = bot.send_message(call.message.chat.id, "Please describe specifically what went wrong.", reply_markup=mk)
    bot.register_next_step_handler(m, report_handling)


def report_handling(message):
    db = get_db()
    user = User.get_or_create(db, message.from_user.id, message.from_user.last_name,
                              message.from_user.first_name, message.from_user.username)
    rec = ReportRecord.new(user, message.text)
    db.add(rec)
    db.commit()
    close_db()
    bot.send_message(message.chat.id,"Thank you for reporting the issues to me!")


@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_report(call):
    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    bot.clear_step_handler_by_chat_id(call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "view_reports")
def choose_report_types(call):
    mk = get_type_report_menu(call.from_user.id)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  reply_markup=mk)


@bot.callback_query_handler(func=lambda call: call.data in ("report_status_NEW", "report_status_REJECTED",
                                                            "report_status_ACCEPTED", "report_status_CLOSED"))
def list_reports(call):
    db = get_db()
    reports = ReportRecord.get_reports(db, call.data)
    close_db()
    mk = get_admin_menu(call)
    for report in reports:
        bot.send_message(chat_id=call.message.chat.id, text=f"Report id: {report.id}\nUser id: {report.user_id}\n"
                                                            f"Timestamp: {report.timestamp}\n\n"
                                                            f"Problem statement:\n{report.text}\n\n"
                                                            f"Status: <b>{report.status}</b>\nLink: {report.link}",
                         parse_mode="html", reply_markup=mk)


@bot.callback_query_handler(func=lambda call: call.data in ("accept_report", "reject_report", "close_report"))
def change_report_status(call):
    db = get_db()
    id = call.message.text.split()[2]
    if call.data == "accept_report":
        m = bot.send_message(call.message.chat.id, "Provide a link to the GitHub issue, please.")
        bot.register_next_step_handler(m, link_handling, id)
    if call.data == "close_report":
        if ReportRecord.get_report_by_id(db, id).status == "ACCEPTED":
            ReportRecord.change_status(db, id, call.data)
            bot.send_message(call.message.chat.id, "The issue has been closed.")
        else:
            bot.send_message(call.message.chat.id, "The issue has not been confirmed yet!")
    if call.data == "reject_report":
        ReportRecord.change_status(db, id, call.data)
        bot.send_message(call.message.chat.id, "The issue has been rejected.")
    close_db()


def link_handling(message, id):
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton(text="Confirm", callback_data=f"accept_link {id}"),
           InlineKeyboardButton(text="Reject", callback_data=f"reject_link {id}"))
    bot.send_message(message.chat.id, text=f"<b>Is the link provided correct?</b>\n<b>Link:</b> {message.text}",
                     parse_mode="html", reply_markup=mk)


@bot.callback_query_handler(func=lambda call: call.data.split()[0] in ("accept_link", "reject_link"))
def accept_link(call):
    db = get_db()
    id = int(call.data.split()[1])
    if call.data.split()[0] == "accept_link":
        ReportRecord.change_status(db, id, "accept_report", call.message.text.split('\n')[1].split()[1])
        bot.send_message(call.message.chat.id, "The issue has been confirmed.")
    else:
        bot.send_message(call.message.chat.id, text="Please provide the link again.")
        bot.register_next_step_handler(call.message, link_handling, id)
    close_db()


@bot.callback_query_handler(func=lambda call: call.data == "back_button")
def back_func(call):
    mk = get_report_menu(call.from_user.id)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  reply_markup=mk)


if __name__ == "__main__":
    print("Copyright (C) 2021-2023 Ilya Bezrukov, Stepan Chizhov, Artem Grishin")
    print("Licensed under GNU GPL-2.0-or-later")
    bot.infinity_polling()  # should be infinity to avoid exceptions (#47)
