/*
    helpers.js
    ----------

    Javascript helpers for the emmett project.

    :copyright: (c) 2014-2018 by Marco Stagni
    :license: BSD-3-Clause
*/
(function($,undefined) {

  var emmett;

  $.emmett = emmett = {
    ajax: function (_url, params, to, _type) {
      /*simple ajax function*/
      query = '';
      if(typeof params == "string") {
        serialized = $(params).serialize();
        if(serialized) {
          query = serialized;
        }
      } else {
        pcs = [];
        if(params != null && params != undefined)
          for(i = 0; i < params.length; i++) {
            q = $("[name=" + params[i] + "]").serialize();
            if(q) {
              pcs.push(q);
            }
          }
        if(pcs.length > 0) {
          query = pcs.join("&");
        }
      }
      $.ajax({
        type: _type ? _type : "GET",
        url: _url,
        data: query,
        success: function (msg) {
          if(to) {
            if(to == ':eval') {
              eval(msg);
            }
            else if(typeof to == 'string') {
              $("#" + to).html(msg);
            }
            else {
              to(msg);
            }
          }
        }
      });
    },

    loadComponents : function() {
      $('[data-emt_remote]').each(function(index) {
          var f = function(obj) {
            var g = function(msg) {
              obj.html(msg);
            };
            return g;
          };
          $.emmett.ajax($(this).data("emt_remote"),[], f($(this)), "GET");
      });
    }
  }

  $(function() {
    emmett.loadComponents();
  });

})($);

ajax = $.emmett.ajax;
