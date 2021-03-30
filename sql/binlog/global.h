/*
   Copyright (c) 2019, 2020, Oracle and/or its affiliates. All rights reserved.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License, version 2.0,
   as published by the Free Software Foundation.

   This program is also distributed with certain software (including
   but not limited to OpenSSL) that is licensed under separate terms,
   as designated in a particular file or component or in included license
   documentation.  The authors of MySQL hereby grant you an additional
   permission to link the program and your derivative works with the
   separately licensed software that they have included with MySQL.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License, version 2.0, for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA */

#ifndef BINLOG_GLOBAL_CONTEXT_H
#define BINLOG_GLOBAL_CONTEXT_H

#include "sql/binlog/monitoring/context.h"

namespace binlog {

/**
  Global context for binary logging.
 */
class Context {
 private:
  Context(const Context &rhs);
  Context &operator=(const Context &rhs);

 protected:
  /**
    Monitoring stats for the binary log.
   */
  monitoring::Context m_monitoring_ctx;

 public:
  Context();
  virtual ~Context();

  monitoring::Context &monitoring_context();
};

extern Context global_context;

}  // namespace binlog

#endif
