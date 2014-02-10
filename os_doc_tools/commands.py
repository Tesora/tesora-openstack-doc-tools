#!/usr/bin/env python

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import argparse
import subprocess
import sys

import os_doc_tools


# NOTE(berendt): check_output as provided in Python 2.7.5 to make script
#                usable with Python < 2.7
def check_output(*popenargs, **kwargs):
    """Run command with arguments and return its output as a byte string.

    If the exit code was non-zero it raises a CalledProcessError.  The
    CalledProcessError object will have the return code in the returncode
    attribute and output in the output attribute.
    """
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise subprocess.CalledProcessError(retcode, cmd, output=output)
    return output


def quote_xml(line):
    """Convert special characters for XML output."""

    line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    if 'DEPRECATED!' in line:
        line = line.replace('DEPRECATED!', '<emphasis>DEPRECATED!</emphasis>')
    elif 'DEPRECATED' in line:
        line = line.replace('DEPRECATED', '<emphasis>DEPRECATED</emphasis>')

    if 'env[' in line:
        line = line.replace('env[', '<code>env[').replace(']', ']</code>')

    return line


def generate_heading(os_command, api_name, os_file):
    """Write DocBook file header.

    :param os_command: client command to document
    :param api_name:   string description of the API of os_command
    :param os_file:    open filehandle for output of DocBook file
    """

    print("Documenting '%s help'" % os_command)

    header = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<chapter xmlns=\"http://docbook.org/ns/docbook\"
    xmlns:xi=\"http://www.w3.org/2001/XInclude\"
    xmlns:xlink=\"http://www.w3.org/1999/xlink\" version=\"5.0\"
    xml:id=\"{0}client_commands\">

    <!-- This file is automatically generated, do not edit -->

    <?dbhtml stop-chunking?>

    <title>{0} commands</title>
    <para>The {0} client is the command-line interface (CLI) for the
         {1} and its extensions.</para>
    <para>For help on a specific <command>{0}</command>
       command, enter:
    </para>
    <screen><prompt>$</prompt> <userinput><command>{0}</command> \
<option>help</option> <replaceable>COMMAND</replaceable></userinput></screen>

    <section xml:id=\"{0}client_command_usage\">
       <title>{0} usage</title>\n"""

    os_file.write(header.format(os_command, api_name))


def is_option(str):
    """Returns True if string specifies an argument."""

    for x in str:
        if not (x.isupper() or x == '_' or x == ','):
            return False

    if str.startswith('DEPRECATED'):
        return False
    return True


def extract_options(line):
    """Extract command or option from line."""

    # We have a command or parameter to handle
    # Differentiate:
    # 1. --version
    # 2. --timeout <seconds>
    # 3. --service <service>, --service-id <service>
    # 4. -v, --verbose
    # 5. -p PORT, --port PORT
    # 6. <backup>              ID of the backup to restore.
    # 7. --alarm-action <Webhook URL>
    # 8.   <NAME or ID>  Name or ID of stack to resume.

    split_line = line.split(None, 2)

    if split_line[0].startswith("-"):
        last_was_option = True
    else:
        last_was_option = False

    if (len(split_line) > 1 and
        ('<' in split_line[0] or
         '<' in split_line[1] or
         '--' in split_line[1] or
         split_line[1].startswith(("-", '<', '{', '[')) or
         is_option(split_line[1]))):

        words = line.split(None)

        i = 0
        while i < len(words) - 1:
            if ('<' in words[i] and
                '>' not in words[i]):
                words[i] += ' ' + words[i + 1]
                del words[i + 1]
            else:
                i += 1

        while len(words) > 1:
            if words[1].startswith('DEPRECATED'):
                break
            if last_was_option:
                if (words[1].startswith(("-", '<', '{', '[')) or
                    is_option(words[1])):
                    words[0] = words[0] + ' ' + words[1]
                    del words[1]
                else:
                    break
            else:
                if words[1].startswith("-"):
                    words[0] = words[0] + ' ' + words[1]
                    del words[1]
                else:
                    break

        w0 = words[0]
        del words[0]
        w1 = ''
        if len(words) > 0:
            w1 = words[0]
            del words[0]
            for w in words:
                w1 += " " + w

        if len(w1) == 0:
            split_line = [w0]
        else:
            split_line = [w0, w1]
    else:
        split_line = line.split(None, 1)

    return split_line


def format_table(title, lines, os_file):
    """Nicely print section of lines."""

    close_entry = False
    os_file.write("  <variablelist wordsize=\"10\">\n")
    if len(title) > 0:
        os_file.write("    <title>%s</title>\n" % title)

    for line in lines:
        if len(line) == 0 or line[0] != ' ':
            break
        # We have to handle these cases:
        # 1. command  Explanation
        # 2. command
        #             Explanation on next line
        # 3. command  Explanation continued
        #             on next line
        # If there are more than 8 spaces, let's treat it as
        # explanation.
        if line.startswith('        '):
            # Explanation
            os_file.write("      %s\n" % quote_xml(line.lstrip(' ')))
            continue
        # Now we have a command or parameter to handle
        split_line = extract_options(line)

        if not close_entry:
            close_entry = True
        else:
            os_file.write("      </para>\n")
            os_file.write("    </listitem>\n")
            os_file.write("  </varlistentry>\n")

        os_file.write("  <varlistentry>\n")
        os_file.write("    <term><command>%s</command></term>\n"
                      % quote_xml(split_line[0]))
        os_file.write("    <listitem>\n")
        os_file.write("      <para>\n")
        if len(split_line) > 1:
            os_file.write("        %s\n" % quote_xml(split_line[1]))

    os_file.write("      </para>\n")
    os_file.write("    </listitem>\n")
    os_file.write("  </varlistentry>\n")
    os_file.write(" </variablelist>\n")

    return


def generate_command(os_command, os_file):
    """Convert os_command --help to DocBook.

    :param os_command: client command to document
    :param os_file:    open filehandle for output of DocBook file
    """

    help_lines = check_output([os_command, "--help"]).split('\n')

    ignore_next_lines = False
    next_line_screen = True
    line_index = -1
    in_screen = False
    for line in help_lines:
        line_index += 1
        xline = quote_xml(line)
        if len(line) > 0 and line[0] != ' ':
            # XXX: Might have whitespace before!!
            if '<subcommands>' in line:
                ignore_next_lines = False
                continue
            if 'Positional arguments' in line:
                ignore_next_lines = True
                next_line_screen = True
                os_file.write("</computeroutput></screen>\n")
                in_screen = False
                format_table('Subcommands', help_lines[line_index + 2:],
                             os_file)
                continue
            if line.startswith(('Optional arguments:', 'Optional:',
                                'Options:', 'optional arguments')):
                if in_screen:
                    os_file.write("</computeroutput></screen>\n")
                    in_screen = False
                os_file.write("    </section>\n")
                os_file.write("    <section ")
                os_file.write("xml:id=\"%sclient_command_optional\">\n"
                              % os_command)
                os_file.write("        <title>%s optional arguments</title>\n"
                              % os_command)
                format_table('', help_lines[line_index + 1:],
                             os_file)
                next_line_screen = True
                ignore_next_lines = True
                continue
            # neutron
            if line.startswith('Commands for API v2.0:'):
                if in_screen:
                    os_file.write("</computeroutput></screen>\n")
                    in_screen = False
                os_file.write("    </section>\n")
                os_file.write("    <section ")
                os_file.write("xml:id=\"%sclient_command_api_2_0\">\n"
                              % os_command)
                os_file.write("        <title>%s API v2.0 commands</title>\n"
                              % os_command)
                format_table('', help_lines[line_index + 1:],
                             os_file)
                next_line_screen = True
                ignore_next_lines = True
                continue
            # swift
            if line.startswith('Examples:'):
                os_file.write("    </section>\n")
                os_file.write("    <section ")
                os_file.write("xml:id=\"%sclient_command_examples\">\n"
                              % os_command)
                os_file.write("        <title>%s examples</title>\n"
                              % os_command)
                next_line_screen = True
                ignore_next_lines = False
                continue
            continue
        if not ignore_next_lines:
            if next_line_screen:
                os_file.write("        <screen><computeroutput>%s\n" % xline)
                next_line_screen = False
                in_screen = True
            elif len(line) > 0:
                os_file.write("%s\n" % (xline))

    if in_screen:
        os_file.write("</computeroutput></screen>\n")

    os_file.write("    </section>\n")


def generate_subcommand(os_command, os_subcommand, os_file):
    """Convert os_command help os_subcommand to DocBook.

    :param os_command: client command to document
    :param os_subcommand: client subcommand to document
    :param os_file:    open filehandle for output of DocBook file
    """

    if os_command == "swift":
        help_lines = check_output([os_command, os_subcommand,
                                   "--help"]).split('\n')
    else:
        help_lines = check_output([os_command, "help",
                                   os_subcommand]).split('\n')

    os_file.write("    <section xml:id=\"%sclient_subcommand_%s\">\n"
                  % (os_command, os_subcommand))
    os_file.write("        <title>%s %s command</title>\n"
                  % (os_command, os_subcommand))

    next_line_screen = True
    line_index = -1
    # Content is:
    # usage...
    #
    # Description
    #
    # Arguments

    in_para = False
    skip_lines = False
    for line in help_lines:
        line_index += 1
        if line.startswith(('Arguments:', 'Positional arguments:',
                            'positional arguments', 'Optional arguments',
                            'optional arguments')):
            if in_para:
                in_para = False
                os_file.write("        </para>")
            if line.startswith(('Positional arguments',
                                'positional arguments')):
                format_table('Positional arguments',
                             help_lines[line_index + 1:], os_file)
                skip_lines = True
                continue
            elif line.startswith(('Optional arguments:',
                                  'optional arguments')):
                format_table('Optional arguments',
                             help_lines[line_index + 1:], os_file)
                break
            else:
                format_table('Arguments', help_lines[line_index + 1:], os_file)
                break
        if skip_lines:
            continue
        if len(line) == 0:
            if not in_para:
                os_file.write("        </computeroutput></screen>\n")
                os_file.write("        <para>\n")
            in_para = True
            continue
        xline = quote_xml(line)
        if next_line_screen:
            os_file.write("        <screen><computeroutput>%s\n" % xline)
            next_line_screen = False
        else:
            os_file.write("%s\n" % (xline))

    if in_para:
        os_file.write("        </para>")
    os_file.write("    </section>\n")


def generate_subcommands(os_command, os_file, blacklist, only_subcommands):
    """Convert os_command help subcommands for all subcommands to DocBook.

    :param os_command: client command to document
    :param os_file:    open filehandle for output of DocBook file
    :param blacklist:  list of elements that will not be documented
    :param only_subcommands: if not empty, list of subcommands to document
    """

    print("Documenting '%s' subcommands..." % os_command)
    blacklist.append("bash-completion")
    blacklist.append("complete")
    blacklist.append("help")
    if not only_subcommands:
        all_options = check_output([os_command,
                                    "bash-completion"]).strip().split()
    else:
        all_options = only_subcommands

    subcommands = [o for o in all_options if not
                   (o.startswith('-') or o in blacklist)]
    for subcommand in sorted(subcommands):
        generate_subcommand(os_command, subcommand, os_file)
    print ("%d subcommands documented." % len(subcommands))


def generate_end(os_file):
    """Finish writing file.

    :param os_file:    open filehandle for output of DocBook file
    """

    print("Finished.\n")
    os_file.write("</chapter>\n")


def document_single_project(os_command):
    """Create documenation for os_command."""

    print ("Documenting '%s'" % os_command)

    blacklist = []
    subcommands = []
    if os_command == 'ceilometer':
        api_name = "OpenStack Telemetry API"
        blacklist = ["alarm-create"]
    elif os_command == 'cinder':
        api_name = "OpenStack Block Storage API"
    elif os_command == 'glance':
        api_name = 'OpenStack Image Service API'
        # Does not know about bash-completion yet, need to specify
        # subcommands manually
        subcommands = ["image-create", "image-delete", "image-list",
                       "image-show", "image-update", "member-create",
                       "member-delete", "member-list"]
    elif os_command == 'heat':
        api_name = "OpenStack Orchestration API"
        blacklist = ["create", "delete", "describe", "event",
                     "gettemplate", "list", "resource",
                     "update", "validate"]
    elif os_command == 'keystone':
        api_name = "OpenStack Identity API"
    elif os_command == 'neutron':
        api_name = "OpenStack Networking API"
    elif os_command == 'nova':
        api_name = "OpenStack Compute API"
        blacklist = ["add-floating-ip", "remove-floating-ip"]
    elif os_command == 'swift':
        api_name = "OpenStack Object Storage API"
        # Does not know about bash-completion yet, need to specify
        # subcommands manually
        subcommands = ["delete", "download", "list", "post",
                       "stat", "upload"]
    elif os_command == 'trove':
        api_name = "OpenStack Database API"
    else:
        print("Not yet handled command")
        sys.exit(-1)

    os_file = open("ch_cli_" + os_command + "_commands.xml",
                   'w')
    generate_heading(os_command, api_name, os_file)
    generate_command(os_command, os_file)
    generate_subcommands(os_command, os_file, blacklist,
                         subcommands)
    generate_end(os_file)
    os_file.close()


def main():
    print("OpenStack Auto Documenting of Commands (using "
          "openstack-doc-tools version %s)\n"
          % os_doc_tools.__version__)

    parser = argparse.ArgumentParser(description="Generate DocBook XML files "
                                     "to document python-PROJECTclients")
    parser.add_argument('client', nargs='?',
                        help="OpenStack command to document")
    parser.add_argument("--all", help="Document all clients ",
                        action="store_true")
    prog_args = parser.parse_args()

    if prog_args.all:
        document_single_project("ceilometer")
        document_single_project("cinder")
        document_single_project("glance")
        document_single_project("heat")
        document_single_project("keystone")
        document_single_project("nova")
        document_single_project("neutron")
        document_single_project("swift")
        document_single_project("trove")
    elif prog_args.client is None:
        print("Pass the name of the client to document as argument.")
        sys.exit(1)
    else:
        document_single_project(prog_args.client)


if __name__ == "__main__":
    sys.exit(main())