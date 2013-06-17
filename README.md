err-pagerduty
============

An Err plugin for interacting with PagerDuty.

Usage
-----

```
!pager register user@example.com
!pager unregister
!pager whoami
!pager oncall or !oncall
!pager trigger <incident message>
!pager ack <incident-id>
!pager resolve <incident-id>
```
ack and resolve commands currently use alphanumeric incident ids

Licence
-------

WTFPL

TODO
----

* Escalate issues to a particular team member
* Resolve issues via numeric ID, in addition to alphanumeric issue ID
* Add notes to incidents
