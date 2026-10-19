create or replace package body ut_ing_delivery as

  c_url        constant varchar2(200) := 'https://data-api.ecb.europa.eu/service/data/YC/x?startPeriod=2026-03-12';
  c_fetched_at constant timestamp := timestamp '2026-03-12 18:00:00.123456';
  -- Bytes that are not valid text in any single-byte character set: CR LF, NUL, UTF-8 euro sign.
  c_payload    constant raw(32) := hextoraw('4b45592c56414c55450d0a00e282ac');
  c_sha256     constant varchar2(64) := rpad('a', 64, 'b');

  function payload return blob is
    l_blob blob;
  begin
    dbms_lob.createtemporary(l_blob, true);
    dbms_lob.writeappend(l_blob, utl_raw.length(c_payload), c_payload);
    return l_blob;
  end payload;

  function stored(p_delivery_id in number) return delivery%rowtype is
    l_row delivery%rowtype;
  begin
    select * into l_row from delivery where delivery_id = p_delivery_id;
    return l_row;
  end stored;

  procedure stores_payload_and_metadata is
    l_row delivery%rowtype;
  begin
    l_row := stored(
      ing_delivery.record_delivery(
        p_source_id       => 'ecb',
        p_run_id          => 'run-1',
        p_request_url     => c_url,
        p_response_status => 200,
        p_fetched_at      => c_fetched_at,
        p_last_modified   => timestamp '2026-03-12 14:05:00',
        p_etag            => '"v1"',
        p_payload         => payload(),
        p_payload_sha256  => c_sha256
      )
    );

    ut.expect(dbms_lob.compare(l_row.payload, payload())).to_equal(0);
    ut.expect(dbms_lob.getlength(l_row.payload)).to_equal(utl_raw.length(c_payload));
    ut.expect(l_row.payload_sha256).to_equal(c_sha256);
    ut.expect(l_row.source_id).to_equal('ecb');
    ut.expect(l_row.run_id).to_equal('run-1');
    ut.expect(l_row.request_url).to_equal(c_url);
    ut.expect(l_row.response_status).to_equal(200);
    ut.expect(l_row.fetched_at).to_equal(c_fetched_at);
    ut.expect(l_row.last_modified).to_equal(timestamp '2026-03-12 14:05:00');
    ut.expect(l_row.etag).to_equal('"v1"');
  end stores_payload_and_metadata;

  procedure records_empty_delivery is
    l_row delivery%rowtype;
  begin
    l_row := stored(ing_delivery.record_delivery('ecb', 'run-1', c_url, 404, c_fetched_at));

    ut.expect(l_row.response_status).to_equal(404);
    ut.expect(l_row.payload).to_be_null();
    ut.expect(l_row.payload_sha256).to_be_null();
    ut.expect(l_row.last_modified).to_be_null();
    ut.expect(l_row.etag).to_be_null();
  end records_empty_delivery;

  procedure every_call_is_a_new_delivery is
    l_first  number;
    l_second number;
  begin
    l_first := ing_delivery.record_delivery('ecb', 'run-1', c_url, 304, c_fetched_at);
    l_second := ing_delivery.record_delivery('ecb', 'run-1', c_url, 304, c_fetched_at);

    ut.expect(l_second).not_to_equal(l_first);
    ut.expect(stored(l_first).response_status).to_equal(304);
    ut.expect(stored(l_second).response_status).to_equal(304);
  end every_call_is_a_new_delivery;

  procedure rejects_payload_without_hash is
    l_delivery_id number;
  begin
    l_delivery_id := ing_delivery.record_delivery(
      'ecb', 'run-1', c_url, 200, c_fetched_at, p_payload => payload()
    );
  end rejects_payload_without_hash;

  procedure rejects_malformed_hash is
    l_delivery_id number;
  begin
    l_delivery_id := ing_delivery.record_delivery(
      'ecb', 'run-1', c_url, 200, c_fetched_at,
      p_payload => payload(), p_payload_sha256 => upper(c_sha256)
    );
  end rejects_malformed_hash;

  procedure reads_deliveries_in_fetch_order is
    l_later   number;
    l_earlier number;
    l_unused  number;
    l_cursor  sys_refcursor;
    l_row     delivery%rowtype;
    l_rows    sys.odcinumberlist := sys.odcinumberlist();
  begin
    l_later := ing_delivery.record_delivery(
      'ecb', 'run-2', c_url, 200, c_fetched_at + interval '1' hour,
      p_payload => payload(), p_payload_sha256 => c_sha256
    );
    l_earlier := ing_delivery.record_delivery('ecb', 'run-1', c_url, 404, c_fetched_at);
    -- Before or at the end of the period, or of another source: not read.
    l_unused := ing_delivery.record_delivery('ecb', 'run-0', c_url, 404, c_fetched_at - interval '1' second);
    l_unused := ing_delivery.record_delivery('ecb', 'run-3', c_url, 404, c_fetched_at + interval '1' day);
    l_unused := ing_delivery.record_delivery('other', 'run-1', c_url, 404, c_fetched_at);

    l_cursor := ing_delivery.get_deliveries('ecb', c_fetched_at, c_fetched_at + interval '1' day);
    loop
      fetch l_cursor into l_row;
      exit when l_cursor%notfound;
      l_rows.extend;
      l_rows(l_rows.count) := l_row.delivery_id;
      if l_row.delivery_id = l_later then
        ut.expect(dbms_lob.compare(l_row.payload, payload())).to_equal(0);
        ut.expect(l_row.payload_sha256).to_equal(c_sha256);
      end if;
    end loop;
    close l_cursor;

    ut.expect(anydata.convertcollection(l_rows)).to_equal(
      anydata.convertcollection(sys.odcinumberlist(l_earlier, l_later))
    );
  end reads_deliveries_in_fetch_order;

end ut_ing_delivery;
/
