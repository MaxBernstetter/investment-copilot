create or replace package ut_ing_delivery as
  --%suite(ing_delivery: raw source deliveries)
  --%rollback(auto)

  --%test(Stores the payload byte for byte with the delivery metadata)
  procedure stores_payload_and_metadata;

  --%test(Records an empty delivery without a payload)
  procedure records_empty_delivery;

  --%test(Every call is a new delivery, also for the same request)
  procedure every_call_is_a_new_delivery;

  --%test(Rejects a payload without its hash)
  --%throws(-2290)
  procedure rejects_payload_without_hash;

  --%test(Rejects a hash that is not lowercase hex SHA-256)
  --%throws(-2290)
  procedure rejects_malformed_hash;

  --%test(Reads the deliveries of a source in a fetch period, in fetch order, with payload)
  procedure reads_deliveries_in_fetch_order;
end ut_ing_delivery;
/
