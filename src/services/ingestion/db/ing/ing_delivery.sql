--liquibase formatted sql

--changeset yieldlens:ing_delivery-spec runOnChange:true endDelimiter:/ stripComments:false
create or replace package ing_delivery authid definer as
  -- The PL/SQL interface of the raw delivery store (bronze layer).
  -- Callers never write the delivery table directly.
  -- The caller owns the transaction: nothing here commits.

  -- Stores one answered source request and returns its delivery id. Every call
  -- is a new delivery, also for the same request: deliveries are never updated.
  -- p_payload is the response body byte for byte, null for an empty delivery
  -- (the source's "no data" answer, 304, or an empty body). p_payload_sha256 is
  -- its SHA-256 in lowercase hex, given exactly when a payload is. Times are UTC.
  function record_delivery(
    p_source_id       in varchar2,
    p_run_id          in varchar2,
    p_request_url     in varchar2,
    p_response_status in pls_integer,
    p_fetched_at      in timestamp,
    p_last_modified   in timestamp default null,
    p_etag            in varchar2  default null,
    p_payload         in blob      default null,
    p_payload_sha256  in varchar2  default null
  ) return delivery.delivery_id%type;

  -- Every delivery of a source fetched in [p_fetched_from, p_fetched_to) (UTC),
  -- payload included, in the order it was fetched (fetched_at, then delivery_id).
  -- The replay source: it reads stored answers, never the source.
  function get_deliveries(
    p_source_id    in varchar2,
    p_fetched_from in timestamp,
    p_fetched_to   in timestamp
  ) return sys_refcursor;
end ing_delivery;
/

--changeset yieldlens:ing_delivery-body runOnChange:true endDelimiter:/ stripComments:false
create or replace package body ing_delivery as

  function record_delivery(
    p_source_id       in varchar2,
    p_run_id          in varchar2,
    p_request_url     in varchar2,
    p_response_status in pls_integer,
    p_fetched_at      in timestamp,
    p_last_modified   in timestamp default null,
    p_etag            in varchar2  default null,
    p_payload         in blob      default null,
    p_payload_sha256  in varchar2  default null
  ) return delivery.delivery_id%type is
    l_delivery_id delivery.delivery_id%type;
  begin
    dbms_application_info.set_module('ing_delivery', 'record_delivery');
    insert into delivery (
      source_id, run_id, request_url, response_status, fetched_at,
      last_modified, etag, payload, payload_sha256
    ) values (
      p_source_id, p_run_id, p_request_url, p_response_status, p_fetched_at,
      p_last_modified, p_etag, p_payload, p_payload_sha256
    )
    returning delivery_id into l_delivery_id;
    dbms_application_info.set_module(null, null);
    return l_delivery_id;
  exception
    when others then
      dbms_application_info.set_module(null, null);
      raise;
  end record_delivery;

  function get_deliveries(
    p_source_id    in varchar2,
    p_fetched_from in timestamp,
    p_fetched_to   in timestamp
  ) return sys_refcursor is
    l_deliveries sys_refcursor;
  begin
    open l_deliveries for
      select delivery_id, source_id, run_id, request_url, response_status, fetched_at,
             last_modified, etag, payload, payload_sha256
        from delivery
       where source_id = p_source_id
         and fetched_at >= p_fetched_from
         and fetched_at < p_fetched_to
       order by fetched_at, delivery_id;
    return l_deliveries;
  end get_deliveries;

end ing_delivery;
/
